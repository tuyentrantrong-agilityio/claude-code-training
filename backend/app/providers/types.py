"""Result types shared by all AI provider interfaces."""

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal


@dataclass(frozen=True)
class TranscriptSegment:
    start_ms: int
    end_ms: int
    speaker_label: str | None
    text: str


@dataclass(frozen=True)
class Transcript:
    language: str
    duration_ms: int
    segments: list[TranscriptSegment]


@dataclass(frozen=True)
class ChatMessage:
    role: Literal["system", "user", "assistant"]
    content: str


@dataclass(frozen=True)
class LlmResult:
    text: str
    input_tokens: int
    output_tokens: int


Embedding = list[float]


@dataclass(frozen=True)
class EmbeddingResult:
    vectors: list[Embedding]
    input_tokens: int
    dimensions: int


@dataclass(frozen=True)
class SpeechAudio:
    mime_type: str
    data: bytes
    duration_ms: int


@dataclass(frozen=True)
class Usage:
    function: str
    provider: str
    units: Decimal
    unit_kind: str
