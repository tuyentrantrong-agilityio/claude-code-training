"""Deepgram batch speech to text over plain httpx (POST /v1/listen)."""

import asyncio
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import httpx

from app.core.settings import Settings, get_settings
from app.providers._http import error_for_status, error_for_transport, log_ok
from app.providers.base import ProviderError
from app.providers.types import Transcript, TranscriptSegment

LISTEN_URL = "https://api.deepgram.com/v1/listen"
UPLOAD_CHUNK_BYTES = 1024 * 1024


async def _file_chunks(path: Path) -> AsyncIterator[bytes]:
    """Yield the file in chunks so long recordings are never held in memory."""
    with path.open("rb") as handle:
        while chunk := await asyncio.to_thread(handle.read, UPLOAD_CHUNK_BYTES):
            yield chunk


def _ms(seconds: Any) -> int:
    return round(float(seconds) * 1000)


def _label(speaker: Any) -> str | None:
    return None if speaker is None else f"speaker_{int(speaker)}"


def _segment(item: dict[str, Any], text: str) -> TranscriptSegment | None:
    text = text.strip()
    if not text:
        return None
    return TranscriptSegment(
        start_ms=_ms(item.get("start", 0)),
        end_ms=_ms(item.get("end", 0)),
        speaker_label=_label(item.get("speaker")),
        text=text,
    )


def _from_utterances(utterances: list[dict[str, Any]]) -> list[TranscriptSegment]:
    found = (_segment(u, str(u.get("transcript", ""))) for u in utterances)
    return [s for s in found if s is not None]


def _from_paragraphs(paragraphs: list[dict[str, Any]]) -> list[TranscriptSegment]:
    found = (
        _segment(p, " ".join(str(s.get("text", "")) for s in p.get("sentences", [])))
        for p in paragraphs
    )
    return [s for s in found if s is not None]


def _from_words(words: list[dict[str, Any]]) -> list[TranscriptSegment]:
    """Group consecutive words of the same speaker into one segment."""
    groups: list[list[dict[str, Any]]] = []
    for word in words:
        if groups and groups[-1][0].get("speaker") == word.get("speaker"):
            groups[-1].append(word)
        else:
            groups.append([word])
    found = (
        _segment(
            {
                "start": g[0].get("start", 0),
                "end": g[-1].get("end", 0),
                "speaker": g[0].get("speaker"),
            },
            " ".join(str(w.get("punctuated_word") or w.get("word", "")) for w in g),
        )
        for g in groups
    )
    return [s for s in found if s is not None]


def parse_response(data: dict[str, Any], language: str) -> Transcript:
    duration_ms = _ms(data.get("metadata", {}).get("duration", 0))
    results = data.get("results", {})
    segments = _from_utterances(results.get("utterances") or [])
    if not segments:
        channels = results.get("channels") or [{}]
        alts = channels[0].get("alternatives") or [{}]
        alt = alts[0]
        segments = _from_paragraphs((alt.get("paragraphs") or {}).get("paragraphs") or [])
        if not segments:
            segments = _from_words(alt.get("words") or [])
        if not segments and str(alt.get("transcript", "")).strip():
            segments = [TranscriptSegment(0, duration_ms, None, str(alt["transcript"]).strip())]
    return Transcript(language=language, duration_ms=duration_ms, segments=segments)


class DeepgramBatchStt:
    name = "deepgram"

    def __init__(
        self, settings: Settings | None = None, client: httpx.AsyncClient | None = None
    ) -> None:
        self._settings = settings or get_settings()
        self._client = client

    def _timeout(self) -> httpx.Timeout:
        short = self._settings.provider_timeout_seconds
        long = self._settings.stt_timeout_seconds
        return httpx.Timeout(connect=short, read=long, write=long, pool=short)

    async def transcribe(self, audio_path: Path, language: str) -> Transcript:
        params = {
            "model": self._settings.deepgram_model,
            "language": language,
            "diarize": "true",
            "punctuate": "true",
            "smart_format": "true",
            "utterances": "true",
        }
        headers = {
            "Authorization": f"Token {self._settings.deepgram_api_key}",
            "Content-Type": "audio/wav",
            "Content-Length": str(audio_path.stat().st_size),
        }
        owned = self._client is None
        client = self._client or httpx.AsyncClient(timeout=self._timeout())
        try:
            response = await client.post(
                LISTEN_URL,
                params=params,
                headers=headers,
                content=_file_chunks(audio_path),
                timeout=self._timeout(),
            )
        except httpx.HTTPError as exc:
            raise error_for_transport(self.name, exc) from exc
        finally:
            if owned:
                await client.aclose()
        if response.status_code >= 400:
            raise error_for_status(self.name, response.status_code, response.headers)
        log_ok(self.name, response.status_code, response.headers)
        try:
            return parse_response(response.json(), language)
        except (ValueError, TypeError, KeyError, AttributeError) as exc:
            raise ProviderError(f"{self.name}: unexpected response format") from exc
