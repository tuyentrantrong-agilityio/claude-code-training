"""Timeout, retry and usage metering around provider calls."""

import asyncio
import uuid
from collections.abc import Awaitable, Callable
from decimal import Decimal
from pathlib import Path
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import get_settings
from app.db.models.org import UsageEvent
from app.providers.base import (
    BatchSttProvider,
    EmbeddingProvider,
    LlmProvider,
    ProviderError,
    ProviderTimeout,
    TtsProvider,
)
from app.providers.types import (
    ChatMessage,
    EmbeddingResult,
    LlmResult,
    SpeechAudio,
    Transcript,
    Usage,
)

Sleep = Callable[[float], Awaitable[None]]
BACKOFF_BASE_SECONDS = 0.5


class _Named(Protocol):
    name: str


class _Metered[P: _Named]:
    def __init__(
        self,
        provider: P,
        session: AsyncSession,
        meeting_id: uuid.UUID | None,
        *,
        timeout: float | None = None,
        max_retries: int | None = None,
        sleep: Sleep = asyncio.sleep,
    ) -> None:
        settings = get_settings()
        self._provider = provider
        self._provider_name = provider.name
        self._session = session
        self._meeting_id = meeting_id
        self._timeout = settings.provider_timeout_seconds if timeout is None else timeout
        self._max_retries = settings.provider_max_retries if max_retries is None else max_retries
        self._sleep = sleep

    async def _call[T](self, make_call: Callable[[], Awaitable[T]]) -> T:
        attempt = 0
        while True:
            try:
                try:
                    async with asyncio.timeout(self._timeout):
                        return await make_call()
                except TimeoutError as exc:
                    raise ProviderTimeout() from exc
            except ProviderError as exc:
                if not exc.retryable or attempt >= self._max_retries:
                    raise
                await self._sleep(BACKOFF_BASE_SECONDS * 2**attempt)
                attempt += 1

    async def _record(self, usages: list[Usage]) -> None:
        for usage in usages:
            self._session.add(
                UsageEvent(
                    meeting_id=self._meeting_id,
                    function=usage.function,
                    provider=usage.provider,
                    units=usage.units,
                    unit_kind=usage.unit_kind,
                )
            )
        await self._session.flush()


class MeteredBatchStt(_Metered[BatchSttProvider]):
    async def transcribe(self, audio_path: Path, language: str) -> Transcript:
        result = await self._call(lambda: self._provider.transcribe(audio_path, language))
        seconds = Decimal(result.duration_ms) / Decimal(1000)
        await self._record([Usage("stt", self._provider_name, seconds, "audio_seconds")])
        return result


class MeteredLlm(_Metered[LlmProvider]):
    async def complete(
        self, messages: list[ChatMessage], *, max_tokens: int, json_mode: bool = False
    ) -> LlmResult:
        result = await self._call(
            lambda: self._provider.complete(messages, max_tokens=max_tokens, json_mode=json_mode)
        )
        name = self._provider_name
        await self._record(
            [
                Usage("llm", name, Decimal(result.input_tokens), "input_tokens"),
                Usage("llm", name, Decimal(result.output_tokens), "output_tokens"),
            ]
        )
        return result


class MeteredEmbedding(_Metered[EmbeddingProvider]):
    @property
    def dimensions(self) -> int:
        return self._provider.dimensions

    async def embed(self, texts: list[str]) -> EmbeddingResult:
        result = await self._call(lambda: self._provider.embed(texts))
        await self._record(
            [Usage("embedding", self._provider_name, Decimal(result.input_tokens), "input_tokens")]
        )
        return result


class MeteredTts(_Metered[TtsProvider]):
    async def synthesize(self, text: str, language: str, voice: str | None = None) -> SpeechAudio:
        result = await self._call(lambda: self._provider.synthesize(text, language, voice))
        await self._record([Usage("tts", self._provider_name, Decimal(len(text)), "characters")])
        return result
