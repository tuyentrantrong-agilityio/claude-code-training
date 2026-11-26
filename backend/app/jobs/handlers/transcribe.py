"""Transcribe job: speech to text with speakers, then queue the recap.

The transcript replaces any earlier one (and its participants) in one transaction, so a
retried job never duplicates rows.
"""

import logging
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.org import Meeting, MeetingParticipant, Recording, TranscriptSegment
from app.jobs import queue
from app.jobs.handlers.common import fail_meeting_on_error, mark_incomplete
from app.jobs.registry import JobContext, NonRetryableJobError, handler
from app.providers.metering import MeteredBatchStt
from app.providers.registry import get_batch_stt
from app.providers.types import Transcript
from app.services.recap import NO_SPEECH_SUMMARY, clear_recap
from app.storage import get_storage

logger = logging.getLogger(__name__)

TRANSCRIBE_ERROR = "Transcription failed."


def clean_segments(transcript: Transcript) -> list[tuple[int, int, str | None, str]]:
    """(start_ms, end_ms, speaker_label, text) in time order; blank text is dropped."""
    rows: list[tuple[int, int, str | None, str]] = []
    for seg in transcript.segments:
        text = seg.text.strip()
        if not text:
            continue
        start = max(seg.start_ms, 0)
        rows.append((start, max(seg.end_ms, start), seg.speaker_label, text))
    return sorted(rows, key=lambda r: r[0])


async def _store_transcript(
    session: AsyncSession, meeting_id: uuid.UUID, rows: list[tuple[int, int, str | None, str]]
) -> None:
    await session.execute(
        delete(TranscriptSegment).where(TranscriptSegment.meeting_id == meeting_id)
    )
    await session.execute(
        delete(MeetingParticipant).where(MeetingParticipant.meeting_id == meeting_id)
    )
    participants: dict[str, MeetingParticipant] = {}
    base = datetime.now(UTC)
    for _, _, label, _ in rows:
        if label is not None and label not in participants:
            participants[label] = MeetingParticipant(
                meeting_id=meeting_id,
                speaker_label=label,
                display_name=f"Speaker {len(participants) + 1}",
                created_at=base + timedelta(microseconds=len(participants)),  # keeps the order
            )
    session.add_all(participants.values())
    await session.flush()
    for seq, (start, end, label, text) in enumerate(rows):
        speaker = participants.get(label) if label is not None else None
        session.add(
            TranscriptSegment(
                meeting_id=meeting_id,
                seq=seq,
                start_ms=start,
                end_ms=end,
                participant_id=speaker.id if speaker else None,
                text=text,
            )
        )
    await session.flush()


@handler("transcribe")
async def transcribe(ctx: JobContext) -> None:
    meeting_id = ctx.meeting_id
    if meeting_id is None:
        raise NonRetryableJobError("transcribe job without a meeting")
    async with ctx.session_factory() as session:
        row = (
            await session.execute(
                select(Meeting.language, Recording.audio_path)
                .join(Recording, Recording.meeting_id == Meeting.id)
                .where(Meeting.id == meeting_id, Meeting.deleted_at.is_(None))
            )
        ).first()
    if row is None:
        logger.warning("transcribe: meeting %s not found (deleted?)", meeting_id)
        return
    language, audio_key = row
    if not audio_key:
        await mark_incomplete(ctx, TRANSCRIBE_ERROR)
        raise NonRetryableJobError("the meeting has no decoded audio")
    audio_path = get_storage().open(audio_key)
    async with fail_meeting_on_error(ctx, TRANSCRIBE_ERROR), ctx.session_factory() as session:
        stt = MeteredBatchStt(get_batch_stt(), session, meeting_id)
        transcript = await stt.transcribe(audio_path, language)
        rows = clean_segments(transcript)
        meeting = await session.scalar(
            select(Meeting).where(Meeting.id == meeting_id, Meeting.deleted_at.is_(None))
        )
        if meeting is None:
            return
        await _store_transcript(session, meeting_id, rows)
        if transcript.duration_ms > (meeting.duration_ms or 0):
            meeting.duration_ms = transcript.duration_ms
        meeting.error = None
        if rows:
            meeting.stage, meeting.status = "summarizing", "processing"
            await queue.enqueue(session, "recap", meeting_id)
        else:
            await clear_recap(session, meeting_id)
            if meeting.summary_edited_at is None:
                meeting.summary = NO_SPEECH_SUMMARY
            meeting.stage, meeting.status = None, "ready"
