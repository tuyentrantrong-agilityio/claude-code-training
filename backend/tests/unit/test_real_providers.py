"""Real provider adapters against httpx.MockTransport. No network."""

import json
import uuid
from collections.abc import Callable
from decimal import Decimal
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import httpx
import pytest

from app.core.settings import Settings, get_settings
from app.providers import registry
from app.providers.anthropic import AnthropicLlm, strip_json_fence
from app.providers.base import (
    BatchSttProvider,
    EmbeddingProvider,
    LlmProvider,
    ProviderError,
    ProviderTimeout,
)
from app.providers.deepgram import DeepgramBatchStt
from app.providers.metering import MeteredLlm
from app.providers.openai_embeddings import MAX_BATCH, OpenAiEmbedding
from app.providers.smoke import main as smoke_main
from app.providers.types import ChatMessage, TokenUsage

Handler = Callable[[httpx.Request], httpx.Response]


def _settings(**kw: Any) -> Settings:
    base: dict[str, Any] = {
        "deepgram_api_key": "dg-key",
        "anthropic_api_key": "an-key",
        "openai_api_key": "oa-key",
    }
    return Settings(**{**base, **kw})


def _client(handler: Handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def _status(code: int) -> Handler:
    return lambda request: httpx.Response(code, json={"error": "x"}, headers={"request-id": "r1"})


def _raise(exc: Exception) -> Handler:
    def handler(request: httpx.Request) -> httpx.Response:
        raise exc

    return handler


ERROR_CASES = [
    (401, False),
    (403, False),
    (400, False),
    (415, False),
    (429, True),
    (500, True),
    (503, True),
    (529, True),
]


# ---------------------------------------------------------------- Deepgram


def _wav(tmp_path: Path) -> Path:
    path = tmp_path / "a.wav"
    path.write_bytes(b"RIFF" + b"\x00" * 3000)
    return path


UTTERANCES = {
    "metadata": {"duration": 12.34},
    "results": {
        "utterances": [
            {"start": 0.5, "end": 3.25, "speaker": 0, "transcript": "Xin chao moi nguoi."},
            {"start": 3.4, "end": 6.0, "speaker": 1, "transcript": "Chao anh, bat dau nhe."},
            {"start": 6.0, "end": 7.0, "speaker": 0, "transcript": "  "},
        ]
    },
}


async def test_deepgram_request_and_utterances(tmp_path: Path) -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=UTTERANCES, headers={"dg-request-id": "d1"})

    path = _wav(tmp_path)
    stt = DeepgramBatchStt(_settings(), client=_client(handler))
    transcript = await stt.transcribe(path, "vi")

    req = seen[0]
    assert req.method == "POST"
    assert str(req.url).startswith("https://api.deepgram.com/v1/listen?")
    assert dict(req.url.params) == {
        "model": "nova-3",
        "language": "vi",
        "diarize": "true",
        "punctuate": "true",
        "smart_format": "true",
        "utterances": "true",
    }
    assert req.headers["authorization"] == "Token dg-key"
    assert req.headers["content-type"] == "audio/wav"
    assert int(req.headers["content-length"]) == path.stat().st_size
    assert req.content == path.read_bytes()
    assert transcript.language == "vi"
    assert transcript.duration_ms == 12340
    assert [(s.start_ms, s.end_ms, s.speaker_label, s.text) for s in transcript.segments] == [
        (500, 3250, "speaker_0", "Xin chao moi nguoi."),
        (3400, 6000, "speaker_1", "Chao anh, bat dau nhe."),
    ]


async def test_deepgram_model_from_settings(tmp_path: Path) -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=UTTERANCES)

    stt = DeepgramBatchStt(_settings(deepgram_model="nova-2"), client=_client(handler))
    await stt.transcribe(_wav(tmp_path), "en")
    assert seen[0].url.params["model"] == "nova-2"
    assert seen[0].url.params["language"] == "en"


async def test_deepgram_fallback_paragraphs(tmp_path: Path) -> None:
    body = {
        "metadata": {"duration": 10},
        "results": {
            "channels": [
                {
                    "alternatives": [
                        {
                            "transcript": "a b c",
                            "paragraphs": {
                                "paragraphs": [
                                    {
                                        "speaker": 1,
                                        "start": 0,
                                        "end": 4.5,
                                        "sentences": [{"text": "Hello."}, {"text": "World."}],
                                    }
                                ]
                            },
                        }
                    ]
                }
            ]
        },
    }
    stt = DeepgramBatchStt(_settings(), client=_client(lambda r: httpx.Response(200, json=body)))
    transcript = await stt.transcribe(_wav(tmp_path), "en")
    assert len(transcript.segments) == 1
    seg = transcript.segments[0]
    assert (seg.start_ms, seg.end_ms, seg.speaker_label) == (0, 4500, "speaker_1")
    assert seg.text == "Hello. World."


async def test_deepgram_fallback_words_grouped_by_speaker(tmp_path: Path) -> None:
    words = [
        {"word": "hi", "punctuated_word": "Hi", "start": 0.0, "end": 0.4, "speaker": 0},
        {"word": "there", "punctuated_word": "there.", "start": 0.4, "end": 0.9, "speaker": 0},
        {"word": "ok", "punctuated_word": "Ok.", "start": 1.0, "end": 1.3, "speaker": 1},
    ]
    body = {
        "metadata": {"duration": 2},
        "results": {"channels": [{"alternatives": [{"transcript": "x", "words": words}]}]},
    }
    stt = DeepgramBatchStt(_settings(), client=_client(lambda r: httpx.Response(200, json=body)))
    transcript = await stt.transcribe(_wav(tmp_path), "en")
    assert [(s.start_ms, s.end_ms, s.speaker_label, s.text) for s in transcript.segments] == [
        (0, 900, "speaker_0", "Hi there."),
        (1000, 1300, "speaker_1", "Ok."),
    ]


async def test_deepgram_transcript_only_fallback(tmp_path: Path) -> None:
    body = {
        "metadata": {"duration": 3},
        "results": {"channels": [{"alternatives": [{"transcript": "just text"}]}]},
    }
    stt = DeepgramBatchStt(_settings(), client=_client(lambda r: httpx.Response(200, json=body)))
    transcript = await stt.transcribe(_wav(tmp_path), "en")
    assert [(s.start_ms, s.end_ms, s.text) for s in transcript.segments] == [(0, 3000, "just text")]


async def test_deepgram_empty_audio_has_no_segments(tmp_path: Path) -> None:
    body = {"metadata": {"duration": 1}, "results": {"channels": [{"alternatives": [{}]}]}}
    stt = DeepgramBatchStt(_settings(), client=_client(lambda r: httpx.Response(200, json=body)))
    assert (await stt.transcribe(_wav(tmp_path), "en")).segments == []


@pytest.mark.parametrize(("code", "retryable"), ERROR_CASES)
async def test_deepgram_error_mapping(tmp_path: Path, code: int, retryable: bool) -> None:
    stt = DeepgramBatchStt(_settings(), client=_client(_status(code)))
    with pytest.raises(ProviderError) as info:
        await stt.transcribe(_wav(tmp_path), "en")
    assert info.value.retryable is retryable
    if code in (401, 403):
        assert "invalid credentials" in str(info.value)


async def test_deepgram_timeout_and_network_errors(tmp_path: Path) -> None:
    stt = DeepgramBatchStt(_settings(), client=_client(_raise(httpx.ReadTimeout("slow"))))
    with pytest.raises(ProviderTimeout) as info:
        await stt.transcribe(_wav(tmp_path), "en")
    assert info.value.retryable is True
    stt = DeepgramBatchStt(_settings(), client=_client(_raise(httpx.ConnectError("down"))))
    with pytest.raises(ProviderError) as info2:
        await stt.transcribe(_wav(tmp_path), "en")
    assert info2.value.retryable is True


async def test_deepgram_garbage_body_is_error(tmp_path: Path) -> None:
    stt = DeepgramBatchStt(
        _settings(), client=_client(lambda r: httpx.Response(200, content=b"not json"))
    )
    with pytest.raises(ProviderError, match="unexpected response"):
        await stt.transcribe(_wav(tmp_path), "en")


# ---------------------------------------------------------------- Anthropic

MESSAGES = [
    ChatMessage("system", "You are terse."),
    ChatMessage("user", "Hello"),
    ChatMessage("assistant", "Hi"),
    ChatMessage("user", "Recap please"),
]


def _complete_body(text: str) -> dict[str, Any]:
    return {
        "content": [{"type": "text", "text": text}],
        "usage": {"input_tokens": 21, "output_tokens": 5},
    }


async def test_anthropic_complete_maps_system_and_usage() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=_complete_body("Hi there"))

    llm = AnthropicLlm(_settings(), client=_client(handler))
    result = await llm.complete(MESSAGES, max_tokens=123)

    req = seen[0]
    assert str(req.url) == "https://api.anthropic.com/v1/messages"
    assert req.headers["x-api-key"] == "an-key"
    assert req.headers["anthropic-version"] == "2023-06-01"
    assert req.headers["content-type"] == "application/json"
    body = json.loads(req.content)
    assert body["model"] == "claude-haiku-5-5"
    assert body["max_tokens"] == 123
    assert body["system"] == "You are terse."
    assert body["messages"] == [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi"},
        {"role": "user", "content": "Recap please"},
    ]
    assert "stream" not in body
    assert (result.text, result.input_tokens, result.output_tokens) == ("Hi there", 21, 5)


async def test_anthropic_json_mode_adds_instruction_and_strips_fence() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=_complete_body('```json\n{"a": 1}\n```'))

    llm = AnthropicLlm(_settings(anthropic_model="claude-sonnet-5-5"), client=_client(handler))
    result = await llm.complete(MESSAGES, max_tokens=10, json_mode=True)
    body = json.loads(seen[0].content)
    assert body["model"] == "claude-sonnet-5-5"
    assert body["system"] == "You are terse.\n\nRespond with a single JSON object only, no prose."
    assert result.text == '{"a": 1}'

    await llm.complete([ChatMessage("user", "x")], max_tokens=10, json_mode=True)
    assert json.loads(seen[1].content)["system"] == (
        "Respond with a single JSON object only, no prose."
    )


def test_strip_json_fence_variants() -> None:
    assert strip_json_fence('```\n{"a":1}\n```') == '{"a":1}'
    assert strip_json_fence('  ```JSON\n{"a":1}```  ') == '{"a":1}'
    assert strip_json_fence('{"a":1}') == '{"a":1}'


def _sse(*events: dict[str, Any]) -> bytes:
    return "".join(f"event: {e['type']}\ndata: {json.dumps(e)}\n\n" for e in events).encode()


STREAM_OK = _sse(
    {"type": "message_start", "message": {"usage": {"input_tokens": 30, "output_tokens": 1}}},
    {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}},
    {"type": "ping"},
    {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "Hel"}},
    {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "lo"}},
    {"type": "content_block_stop", "index": 0},
    {"type": "message_delta", "delta": {"stop_reason": "end_turn"}, "usage": {"output_tokens": 9}},
    {"type": "message_stop"},
)


async def test_anthropic_stream_pieces_and_usage() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, content=STREAM_OK, headers={"content-type": "text/event-stream"})

    llm = AnthropicLlm(_settings(), client=_client(handler))
    assert llm.last_usage is None
    pieces = [p async for p in llm.stream(MESSAGES, max_tokens=50)]
    assert pieces == ["Hel", "lo"]
    assert json.loads(seen[0].content)["stream"] is True
    assert llm.last_usage == TokenUsage(30, 9)


async def test_anthropic_stream_error_event() -> None:
    content = _sse(
        {"type": "message_start", "message": {"usage": {"input_tokens": 3}}},
        {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "A"}},
        {"type": "error", "error": {"type": "overloaded_error", "message": "Overloaded"}},
    )
    llm = AnthropicLlm(_settings(), client=_client(lambda r: httpx.Response(200, content=content)))
    got: list[str] = []
    with pytest.raises(ProviderError) as info:
        async for piece in llm.stream(MESSAGES, max_tokens=5):
            got.append(piece)
    assert got == ["A"]
    assert info.value.retryable is True
    assert llm.last_usage is None

    bad = _sse({"type": "error", "error": {"type": "invalid_request_error"}})
    llm = AnthropicLlm(_settings(), client=_client(lambda r: httpx.Response(200, content=bad)))
    with pytest.raises(ProviderError) as info2:
        [p async for p in llm.stream(MESSAGES, max_tokens=5)]
    assert info2.value.retryable is False


@pytest.mark.parametrize(("code", "retryable"), ERROR_CASES)
async def test_anthropic_error_mapping(code: int, retryable: bool) -> None:
    llm = AnthropicLlm(_settings(), client=_client(_status(code)))
    with pytest.raises(ProviderError) as info:
        await llm.complete(MESSAGES, max_tokens=5)
    assert info.value.retryable is retryable
    with pytest.raises(ProviderError) as info2:
        [p async for p in llm.stream(MESSAGES, max_tokens=5)]
    assert info2.value.retryable is retryable


async def test_anthropic_timeout_and_network() -> None:
    llm = AnthropicLlm(_settings(), client=_client(_raise(httpx.ConnectTimeout("t"))))
    with pytest.raises(ProviderTimeout):
        await llm.complete(MESSAGES, max_tokens=5)
    llm = AnthropicLlm(_settings(), client=_client(_raise(httpx.ReadError("r"))))
    with pytest.raises(ProviderError) as info:
        [p async for p in llm.stream(MESSAGES, max_tokens=5)]
    assert info.value.retryable is True


# ---------------------------------------------------------------- OpenAI embeddings


def _embed_handler(seen: list[httpx.Request]) -> Handler:
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        inputs = json.loads(request.content)["input"]
        # Return rows reversed to prove the adapter sorts by index.
        rows = [{"index": i, "embedding": [float(i), 0.5]} for i in range(len(inputs))]
        rows.reverse()
        return httpx.Response(200, json={"data": rows, "usage": {"prompt_tokens": len(inputs)}})

    return handler


async def test_openai_embeddings_request_and_order() -> None:
    seen: list[httpx.Request] = []
    emb = OpenAiEmbedding(_settings(embedding_dimensions=2), client=_client(_embed_handler(seen)))
    assert emb.name == "openai"
    result = await emb.embed(["a", "b", "c"])

    req = seen[0]
    assert str(req.url) == "https://api.openai.com/v1/embeddings"
    assert req.headers["authorization"] == "Bearer oa-key"
    body = json.loads(req.content)
    assert body["model"] == "text-embedding-3-small"
    assert body["dimensions"] == 2
    assert body["input"] == ["a", "b", "c"]
    assert result.vectors == [[0.0, 0.5], [1.0, 0.5], [2.0, 0.5]]
    assert result.input_tokens == 3
    assert result.dimensions == 2


async def test_openai_embeddings_batches_over_limit() -> None:
    seen: list[httpx.Request] = []
    emb = OpenAiEmbedding(_settings(), client=_client(_embed_handler(seen)))
    texts = [f"t{i}" for i in range(MAX_BATCH * 2 + 5)]
    result = await emb.embed(texts)
    sizes = [len(json.loads(r.content)["input"]) for r in seen]
    assert sizes == [256, 256, 5]
    assert len(result.vectors) == len(texts)
    assert result.input_tokens == len(texts)
    assert result.dimensions == 1536


async def test_openai_embeddings_empty_makes_no_call() -> None:
    seen: list[httpx.Request] = []
    emb = OpenAiEmbedding(_settings(), client=_client(_embed_handler(seen)))
    result = await emb.embed([])
    assert result.vectors == [] and result.input_tokens == 0 and seen == []


@pytest.mark.parametrize(("code", "retryable"), ERROR_CASES)
async def test_openai_error_mapping(code: int, retryable: bool) -> None:
    emb = OpenAiEmbedding(_settings(), client=_client(_status(code)))
    with pytest.raises(ProviderError) as info:
        await emb.embed(["a"])
    assert info.value.retryable is retryable


async def test_openai_timeout() -> None:
    emb = OpenAiEmbedding(_settings(), client=_client(_raise(httpx.ReadTimeout("t"))))
    with pytest.raises(ProviderTimeout):
        await emb.embed(["a"])


# ---------------------------------------------------------------- registry and metering


def test_adapters_conform_to_protocols() -> None:
    assert isinstance(DeepgramBatchStt(_settings()), BatchSttProvider)
    assert isinstance(AnthropicLlm(_settings()), LlmProvider)
    assert isinstance(OpenAiEmbedding(_settings()), EmbeddingProvider)


def test_registry_selects_real_providers_with_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    env = {
        "PROVIDER_STT_BATCH": "deepgram",
        "PROVIDER_LLM": "anthropic",
        "PROVIDER_EMBEDDING": "openai",
        "DEEPGRAM_API_KEY": "k1",
        "ANTHROPIC_API_KEY": "k2",
        "OPENAI_API_KEY": "k3",
    }
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()
    try:
        assert isinstance(registry.get_batch_stt(), DeepgramBatchStt)
        assert isinstance(registry.get_llm(), AnthropicLlm)
        assert isinstance(registry.get_embedding(), OpenAiEmbedding)
    finally:
        monkeypatch.undo()
        get_settings.cache_clear()


@pytest.mark.parametrize(
    ("choice", "getter", "message"),
    [
        ("PROVIDER_STT_BATCH=deepgram", registry.get_batch_stt, "DEEPGRAM_API_KEY"),
        ("PROVIDER_LLM=anthropic", registry.get_llm, "ANTHROPIC_API_KEY"),
        ("PROVIDER_EMBEDDING=openai", registry.get_embedding, "OPENAI_API_KEY"),
    ],
)
def test_registry_missing_key_fails_fast(
    monkeypatch: pytest.MonkeyPatch, choice: str, getter: Callable[[], object], message: str
) -> None:
    name, value = choice.split("=")
    monkeypatch.setenv(name, value)
    for key in ("DEEPGRAM_API_KEY", "ANTHROPIC_API_KEY", "OPENAI_API_KEY"):
        monkeypatch.setenv(key, "")
    get_settings.cache_clear()
    try:
        with pytest.raises(ValueError, match=f"{choice} needs {message}"):
            getter()
    finally:
        monkeypatch.undo()
        get_settings.cache_clear()


class _Session:
    def __init__(self) -> None:
        self.added: list[Any] = []
        self.flush = AsyncMock()

    def add(self, row: Any) -> None:
        self.added.append(row)


def _tokens(session: _Session) -> dict[str, Decimal]:
    return {row.unit_kind: row.units for row in session.added}


async def test_metered_stream_uses_adapter_last_usage() -> None:
    llm = AnthropicLlm(
        _settings(), client=_client(lambda r: httpx.Response(200, content=STREAM_OK))
    )
    session = _Session()
    metered = MeteredLlm(llm, session, uuid.uuid4(), timeout=5)  # type: ignore[arg-type]
    pieces = [p async for p in metered.stream([ChatMessage("user", "one two three")], max_tokens=9)]
    assert pieces == ["Hel", "lo"]
    assert _tokens(session) == {"input_tokens": Decimal(30), "output_tokens": Decimal(9)}


async def test_metered_stream_falls_back_to_word_counts_without_last_usage() -> None:
    from app.providers.fakes import FakeLlm

    session = _Session()
    metered = MeteredLlm(FakeLlm(), session, uuid.uuid4(), timeout=5)  # type: ignore[arg-type]
    [p async for p in metered.stream([ChatMessage("user", "one two three")], max_tokens=9)]
    assert _tokens(session)["input_tokens"] == Decimal(3)
    assert _tokens(session)["output_tokens"] == Decimal(5)


# ---------------------------------------------------------------- smoke


def test_smoke_refuses_fake_providers(capsys: pytest.CaptureFixture[str]) -> None:
    assert smoke_main(["--llm", "--embedding"]) == 1
    out = capsys.readouterr().out
    assert "llm: provider is fake" in out
    assert "embedding: provider is fake" in out


def test_smoke_requires_a_choice() -> None:
    with pytest.raises(SystemExit):
        smoke_main([])
