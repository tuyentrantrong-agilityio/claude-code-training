"""Decode job: convert the upload to mono 16 kHz 16-bit WAV and read its duration.

The meeting stage stays "uploading" while decoding (the stage list has no "decoding"), so
a failed decode is retried from the "uploading" stage.
"""

import asyncio
import logging
import tempfile
from pathlib import Path

from sqlalchemy import select, update

from app.core.settings import get_settings
from app.db.models.org import Meeting, Recording
from app.jobs import queue
from app.jobs.registry import JobContext, NonRetryableJobError, handler
from app.storage import get_storage, iter_file, meeting_key

logger = logging.getLogger(__name__)

DECODE_ERROR = "Could not read the audio in this file."
AUDIO_NAME = "audio.wav"
STDERR_TAIL = 500


class DecodeError(Exception):
    pass


async def _run(argv: list[str], timeout: float) -> tuple[int, str, str]:
    """Run a program without a shell; return (exit code, stdout, stderr)."""
    proc = await asyncio.create_subprocess_exec(
        *argv,
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except TimeoutError:
        proc.kill()
        await proc.wait()
        raise DecodeError("timed out") from None
    return proc.returncode or 0, out.decode(errors="replace"), err.decode(errors="replace")


async def convert_to_wav(source: Path, target: Path) -> int:
    """Write target as mono 16 kHz 16-bit WAV and return its duration in ms."""
    settings = get_settings()
    code, _, err = await _run(
        [
            settings.ffmpeg_path,
            "-nostdin",
            "-y",
            "-v",
            "error",
            "-i",
            str(source),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-c:a",
            "pcm_s16le",
            "-f",
            "wav",
            str(target),
        ],
        settings.decode_timeout_seconds,
    )
    if code != 0:
        raise DecodeError(f"ffmpeg exited with {code}: {err[-STDERR_TAIL:]}")
    code, out, err = await _run(
        [
            settings.ffprobe_path,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(target),
        ],
        settings.decode_timeout_seconds,
    )
    if code != 0:
        raise DecodeError(f"ffprobe exited with {code}: {err[-STDERR_TAIL:]}")
    try:
        duration_ms = round(float(out.strip()) * 1000)
    except ValueError:
        raise DecodeError(f"ffprobe gave no duration: {out.strip()[:50]!r}") from None
    if duration_ms <= 0:
        raise DecodeError("the file has no audio")
    return duration_ms


@handler("decode")
async def decode(ctx: JobContext) -> None:
    meeting_id = ctx.meeting_id
    if meeting_id is None:
        raise NonRetryableJobError("decode job without a meeting")
    async with ctx.session_factory() as session:
        original = await session.scalar(
            select(Recording.original_path).where(Recording.meeting_id == meeting_id)
        )
    if original is None:
        logger.warning("decode: meeting %s has no recording (deleted?)", meeting_id)
        return
    storage = get_storage()
    audio_key = meeting_key(ctx.schema_name, meeting_id, AUDIO_NAME)
    try:
        with tempfile.TemporaryDirectory(prefix="recapz-decode-") as tmp:
            target = Path(tmp) / AUDIO_NAME
            duration_ms = await convert_to_wav(storage.open(original), target)
            await storage.save(iter_file(target), audio_key)
    except FileNotFoundError as exc:
        # Missing ffmpeg binary or missing original: not a problem with the audio itself.
        raise RuntimeError(f"decode could not start: {exc}") from exc
    except DecodeError as exc:
        async with ctx.session_factory() as session:
            await session.execute(
                update(Meeting)
                .where(Meeting.id == meeting_id)
                .values(status="incomplete", error=DECODE_ERROR)
            )
        raise NonRetryableJobError(str(exc)) from exc
    async with ctx.session_factory() as session:
        await session.execute(
            update(Recording).where(Recording.meeting_id == meeting_id).values(audio_path=audio_key)
        )
        await session.execute(
            update(Meeting)
            .where(Meeting.id == meeting_id)
            .values(duration_ms=duration_ms, stage="transcribing", status="processing", error=None)
        )
        await queue.enqueue(session, "transcribe", meeting_id)
