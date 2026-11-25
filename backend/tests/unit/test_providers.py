import asyncio
import io
import json
import math
import shutil
import uuid
import wave
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import pytest

from app.core.settings import get_settings
from app.providers import registry
from app.providers.base import (
    BatchSttProvider,
    EmbeddingProvider,
    LlmProvider,
    ProviderError,
    ProviderTimeout,
    StreamingSttProvider,
    TtsProvider,
)
from app.providers.fakes import FakeBatchStt, FakeEmbedding, FakeLlm, FakeStreamingStt, FakeTts
from app.providers.metering import MeteredLlm
from app.providers.types import ChatMessage

FIXTURES = Path(__file__).parent.parent / "fixtures"


def test_fakes_conform_to_protocols() -> None:
    assert isinstance(FakeBatchStt(), BatchSttProvider)
    assert isinstance(FakeStreamingStt(), StreamingSttProvider)
    assert isinstance(FakeLlm(), LlmProvider)
    assert isinstance(FakeEmbedding(), EmbeddingProvider)
    assert isinstance(FakeTts(), TtsProvider)
    assert FakeLlm().name == "fake"


async def test_embedding_deterministic_and_normalized() -> None:
    fake = FakeEmbedding(dimensions=16)
    a = await fake.embed(["hello world", "other"])
    b = await fake.embed(["hello world"])
    assert a.dimensions == 16
    assert a.vectors[0] == b.vectors[0]
    assert a.vectors[0] != a.vectors[1]
    for vec in a.vectors:
        assert len(vec) == 16
        assert math.isclose(math.sqrt(sum(v * v for v in vec)), 1.0, rel_tol=1e-9)
    assert a.input_tokens == 3
    assert FakeEmbedding().dimensions == 8


async def test_llm_recap_json_uses_prompt_timestamps() -> None:
    prompt = "RECAP_JSON\n[at_ms=1500] hello\n[at_ms=42000] bye\n[at_ms=90000] end"
    res = await FakeLlm().complete(
        [ChatMessage("system", "be brief"), ChatMessage("user", prompt)],
        max_tokens=100,
        json_mode=True,
    )
    data = json.loads(res.text)
    for key in ("summary", "follow_ups", "key_points", "chapters", "highlights", "questions"):
        assert key in data
    allowed = {1500, 42000, 90000}
    items = [*data["follow_ups"], *data["key_points"], *data["chapters"], *data["highlights"]]
    assert items
    assert {i["at_ms"] for i in items} <= allowed
    assert {"text", "owner", "at_ms"} <= set(data["follow_ups"][0])
    assert res.output_tokens == len(res.text.split())


async def test_llm_plain_and_stream() -> None:
    fake = FakeLlm()
    res = await fake.complete([ChatMessage("user", "one two three")], max_tokens=10)
    assert res.text == fake.canned
    assert res.input_tokens == 3
    json_res = await fake.complete([ChatMessage("user", "x")], max_tokens=10, json_mode=True)
    assert json.loads(json_res.text)
    parts = [p async for p in fake.stream([ChatMessage("user", "x")], max_tokens=10)]
    assert "".join(parts).strip() == fake.canned


async def test_batch_stt_reads_sidecar(tmp_path: Path) -> None:
    audio = tmp_path / "sample.wav"
    audio.write_bytes(b"")
    shutil.copy(FIXTURES / "sample.wav.transcript.json", tmp_path / "sample.wav.transcript.json")
    result = await FakeBatchStt().transcribe(audio, "vi")
    assert result.language == "en"
    assert result.duration_ms == 12000
    assert [s.speaker_label for s in result.segments] == ["Speaker 1", "Speaker 2"]
    assert result.segments[1].end_ms == 12000


async def test_batch_stt_without_sidecar(tmp_path: Path) -> None:
    result = await FakeBatchStt().transcribe(tmp_path / "standup.mp3", "vi")
    assert result.language == "vi"
    assert len(result.segments) == 2
    assert "standup" in result.segments[0].text


async def test_streaming_stt_one_segment_per_chunk() -> None:
    async def chunks() -> AsyncIterator[bytes]:
        for n in (3, 5, 7):
            yield b"x" * n

    segs = [s async for s in FakeStreamingStt().stream(chunks(), "en")]
    assert [s.start_ms for s in segs] == [0, 1000, 2000]
    assert segs[1].end_ms == 2000


async def test_tts_returns_silent_wav() -> None:
    res = await FakeTts().synthesize("hello there", "en")
    assert res.mime_type == "audio/wav"
    assert res.duration_ms == len("hello there") * 50
    with wave.open(io.BytesIO(res.data)) as wav:
        assert wav.getnframes() > 0


def _set(monkeypatch: pytest.MonkeyPatch, **env: str) -> None:
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()


def test_registry_defaults_to_fakes() -> None:
    assert isinstance(registry.get_batch_stt(), FakeBatchStt)
    assert isinstance(registry.get_streaming_stt(), FakeStreamingStt)
    assert isinstance(registry.get_llm(), FakeLlm)
    assert isinstance(registry.get_embedding(), FakeEmbedding)
    assert isinstance(registry.get_tts(), FakeTts)


def test_registry_unknown_name(monkeypatch: pytest.MonkeyPatch) -> None:
    _set(monkeypatch, PROVIDER_LLM="nope")
    try:
        with pytest.raises(ValueError, match=r"nope.*known: fake"):
            registry.get_llm()
    finally:
        monkeypatch.undo()
        get_settings.cache_clear()


def test_register_provider_hook(monkeypatch: pytest.MonkeyPatch) -> None:
    registry.register_provider("tts", "custom", lambda: FakeTts(fail_times=1))
    try:
        _set(monkeypatch, PROVIDER_TTS="custom")
        assert registry.get_tts().name == "fake"
        assert isinstance(registry.get_tts(), FakeTts)
    finally:
        registry._FACTORIES["tts"].pop("custom", None)
        monkeypatch.undo()
        get_settings.cache_clear()


def test_settings_defaults() -> None:
    s = get_settings()
    assert s.provider_timeout_seconds == 60
    assert s.provider_max_retries == 2


class _FakeSession:
    """Stands in for AsyncSession; records added rows."""

    def __init__(self) -> None:
        self.added: list[Any] = []
        self.flush = AsyncMock()

    def add(self, row: Any) -> None:
        self.added.append(row)


def _metered(
    llm: Any, sleeps: list[float], *, max_retries: int = 2, timeout: float = 5
) -> tuple[MeteredLlm, _FakeSession]:
    session = _FakeSession()

    async def sleep(seconds: float) -> None:
        sleeps.append(seconds)

    wrapper = MeteredLlm(
        llm,
        session,
        uuid.uuid4(),
        timeout=timeout,
        max_retries=max_retries,
        sleep=sleep,  # type: ignore[arg-type]
    )
    return wrapper, session


MSGS = [ChatMessage("user", "hi there")]


async def test_retry_fails_twice_then_succeeds() -> None:
    llm = FakeLlm(fail_times=2)
    sleeps: list[float] = []
    wrapper, session = _metered(llm, sleeps)
    res = await wrapper.complete(MSGS, max_tokens=10)
    assert res.text == llm.canned
    assert llm.calls == 3
    assert sleeps == [0.5, 1.0]
    assert len(session.added) == 2


async def test_retries_exhausted() -> None:
    llm = FakeLlm(fail_times=5)
    sleeps: list[float] = []
    wrapper, session = _metered(llm, sleeps, max_retries=2)
    with pytest.raises(ProviderError):
        await wrapper.complete(MSGS, max_tokens=10)
    assert llm.calls == 3
    assert sleeps == [0.5, 1.0]
    assert session.added == []


async def test_non_retryable_not_retried() -> None:
    llm = FakeLlm(fail_times=1, retryable=False)
    sleeps: list[float] = []
    wrapper, session = _metered(llm, sleeps)
    with pytest.raises(ProviderError) as info:
        await wrapper.complete(MSGS, max_tokens=10)
    assert info.value.retryable is False
    assert llm.calls == 1
    assert sleeps == []
    assert session.added == []


class _SlowLlm(FakeLlm):
    async def complete(
        self, messages: list[ChatMessage], *, max_tokens: int, json_mode: bool = False
    ) -> Any:
        self.calls += 1
        await asyncio.sleep(10)


async def test_timeout_becomes_retryable_provider_timeout() -> None:
    llm = _SlowLlm()
    sleeps: list[float] = []
    wrapper, session = _metered(llm, sleeps, max_retries=1, timeout=0.01)
    with pytest.raises(ProviderTimeout) as info:
        await wrapper.complete(MSGS, max_tokens=10)
    assert info.value.retryable is True
    assert llm.calls == 2
    assert sleeps == [0.5]
    assert session.added == []
