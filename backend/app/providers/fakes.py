"""Deterministic fake providers. They never touch the network."""

import hashlib
import io
import json
import math
import re
import wave
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from app.providers.base import ProviderError
from app.providers.types import (
    ChatMessage,
    EmbeddingResult,
    LlmResult,
    SpeechAudio,
    Transcript,
    TranscriptSegment,
)

RECAP_MARKER = "RECAP_JSON"
_AT_MS_RE = re.compile(r"\[at_ms=(\d+)\]")


class _Failing:
    """Mixin: fail the first `fail_times` calls with a ProviderError."""

    name = "fake"

    def __init__(self, *, fail_times: int = 0, retryable: bool = True) -> None:
        self.fail_times = fail_times
        self.retryable = retryable
        self.calls = 0

    def _maybe_fail(self) -> None:
        self.calls += 1
        if self.calls <= self.fail_times:
            raise ProviderError(f"fake failure {self.calls}", retryable=self.retryable)


def _words(text: str) -> int:
    return len(text.split())


class FakeBatchStt(_Failing):
    async def transcribe(self, audio_path: Path, language: str) -> Transcript:
        self._maybe_fail()
        sidecar = audio_path.with_name(audio_path.name + ".transcript.json")
        if sidecar.is_file():
            data = json.loads(sidecar.read_text(encoding="utf-8"))
            return Transcript(
                language=data["language"],
                duration_ms=int(data["duration_ms"]),
                segments=[
                    TranscriptSegment(
                        start_ms=int(s["start_ms"]),
                        end_ms=int(s["end_ms"]),
                        speaker_label=s.get("speaker_label"),
                        text=s["text"],
                    )
                    for s in data["segments"]
                ],
            )
        stem = audio_path.stem
        return Transcript(
            language=language,
            duration_ms=10_000,
            segments=[
                TranscriptSegment(0, 5_000, "Speaker 1", f"Opening remarks for {stem}."),
                TranscriptSegment(5_000, 10_000, "Speaker 2", f"Closing remarks for {stem}."),
            ],
        )


class FakeStreamingStt(_Failing):
    chunk_ms = 1_000

    async def stream(
        self, chunks: AsyncIterator[bytes], language: str
    ) -> AsyncIterator[TranscriptSegment]:
        self._maybe_fail()
        index = 0
        async for chunk in chunks:
            start = index * self.chunk_ms
            yield TranscriptSegment(
                start, start + self.chunk_ms, "Speaker 1", f"chunk {index + 1} ({len(chunk)} bytes)"
            )
            index += 1


def _recap_json(prompt: str) -> str:
    stamps = [int(m) for m in _AT_MS_RE.findall(prompt)]

    def at(i: int) -> int | None:
        return stamps[i % len(stamps)] if stamps else None

    recap: dict[str, Any] = {
        "summary": "Fake recap of the meeting.",
        "follow_ups": [
            {"text": f"Follow up {i + 1}", "owner": "Speaker 1", "at_ms": at(i)}
            for i in range(min(2, len(stamps)))
        ],
        "key_points": [
            {"at_ms": at(i), "text": f"Key point {i + 1}"} for i in range(min(3, len(stamps)))
        ],
        "chapters": [
            {"at_ms": at(i), "title": f"Chapter {i + 1}", "text": None}
            for i in range(min(2, len(stamps)))
        ],
        "highlights": [
            {"at_ms": at(i), "text": f"Highlight {i + 1}"} for i in range(min(2, len(stamps)))
        ],
        "questions": [
            {"at_ms": at(i), "text": f"Question {i + 1}?"} for i in range(min(1, len(stamps)))
        ],
    }
    return json.dumps(recap)


class FakeLlm(_Failing):
    canned = "This is a fake response."

    def _text(self, messages: list[ChatMessage], json_mode: bool) -> str:
        if json_mode:
            last_user = next((m.content for m in reversed(messages) if m.role == "user"), "")
            if RECAP_MARKER in last_user:
                return _recap_json(last_user)
            return json.dumps({"text": self.canned})
        return self.canned

    async def complete(
        self, messages: list[ChatMessage], *, max_tokens: int, json_mode: bool = False
    ) -> LlmResult:
        self._maybe_fail()
        text = self._text(messages, json_mode)
        return LlmResult(
            text=text,
            input_tokens=sum(_words(m.content) for m in messages),
            output_tokens=_words(text),
        )

    async def stream(self, messages: list[ChatMessage], *, max_tokens: int) -> AsyncIterator[str]:
        self._maybe_fail()
        for word in self.canned.split():
            yield word + " "


class FakeEmbedding(_Failing):
    def __init__(self, dimensions: int = 8, *, fail_times: int = 0, retryable: bool = True) -> None:
        super().__init__(fail_times=fail_times, retryable=retryable)
        self.dimensions = dimensions

    def _vector(self, text: str) -> list[float]:
        raw = [
            int.from_bytes(hashlib.sha256(f"{i}:{text}".encode()).digest()[:8], "big") / 2**63 - 1.0
            for i in range(self.dimensions)
        ]
        norm = math.sqrt(sum(v * v for v in raw)) or 1.0
        return [v / norm for v in raw]

    async def embed(self, texts: list[str]) -> EmbeddingResult:
        self._maybe_fail()
        return EmbeddingResult(
            vectors=[self._vector(t) for t in texts],
            input_tokens=sum(_words(t) for t in texts),
            dimensions=self.dimensions,
        )


class FakeTts(_Failing):
    sample_rate = 1_000
    ms_per_char = 50

    async def synthesize(self, text: str, language: str, voice: str | None = None) -> SpeechAudio:
        self._maybe_fail()
        duration_ms = max(100, len(text) * self.ms_per_char)
        frames = self.sample_rate * duration_ms // 1_000
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(1)
            wav.setframerate(self.sample_rate)
            wav.writeframes(b"\x80" * frames)
        return SpeechAudio(mime_type="audio/wav", data=buf.getvalue(), duration_ms=duration_ms)
