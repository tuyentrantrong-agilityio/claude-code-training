"""Provider interfaces (one Protocol per AI function) and error types."""

from collections.abc import AsyncIterator
from pathlib import Path
from typing import Protocol, runtime_checkable

from app.providers.types import (
    ChatMessage,
    EmbeddingResult,
    LlmResult,
    SpeechAudio,
    Transcript,
    TranscriptSegment,
)


class ProviderError(Exception):
    """A provider call failed. Retryable errors are retried by the metering wrapper."""

    def __init__(self, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.retryable = retryable


class ProviderTimeout(ProviderError):
    def __init__(self, message: str = "provider call timed out") -> None:
        super().__init__(message, retryable=True)


@runtime_checkable
class BatchSttProvider(Protocol):
    name: str

    async def transcribe(self, audio_path: Path, language: str) -> Transcript: ...


@runtime_checkable
class StreamingSttProvider(Protocol):
    name: str

    def stream(
        self, chunks: AsyncIterator[bytes], language: str
    ) -> AsyncIterator[TranscriptSegment]: ...


@runtime_checkable
class LlmProvider(Protocol):
    name: str

    async def complete(
        self, messages: list[ChatMessage], *, max_tokens: int, json_mode: bool = False
    ) -> LlmResult: ...

    def stream(self, messages: list[ChatMessage], *, max_tokens: int) -> AsyncIterator[str]: ...


@runtime_checkable
class EmbeddingProvider(Protocol):
    name: str
    dimensions: int

    async def embed(self, texts: list[str]) -> EmbeddingResult: ...


@runtime_checkable
class TtsProvider(Protocol):
    name: str

    async def synthesize(
        self, text: str, language: str, voice: str | None = None
    ) -> SpeechAudio: ...
