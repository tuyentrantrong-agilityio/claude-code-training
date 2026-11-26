"""Settings-driven provider selection. Real adapters plug in via register_provider."""

from collections.abc import Callable
from typing import Literal, cast

from app.core.settings import get_settings
from app.providers import fakes
from app.providers.anthropic import AnthropicLlm
from app.providers.base import (
    BatchSttProvider,
    EmbeddingProvider,
    LlmProvider,
    StreamingSttProvider,
    TtsProvider,
)
from app.providers.deepgram import DeepgramBatchStt
from app.providers.openai_embeddings import OpenAiEmbedding

Function = Literal["stt_batch", "stt_stream", "llm", "embedding", "tts"]

_FACTORIES: dict[str, dict[str, Callable[[], object]]] = {
    "stt_batch": {"fake": fakes.FakeBatchStt},
    "stt_stream": {"fake": fakes.FakeStreamingStt},
    "llm": {"fake": fakes.FakeLlm},
    "embedding": {"fake": fakes.FakeEmbedding},
    "tts": {"fake": fakes.FakeTts},
}


def register_provider(function: Function, name: str, factory: Callable[[], object]) -> None:
    _FACTORIES[function][name] = factory


def _build(function: Function, name: str) -> object:
    known = _FACTORIES[function]
    if name not in known:
        raise ValueError(f"unknown {function} provider {name!r}; known: {', '.join(sorted(known))}")
    return known[name]()


def get_batch_stt() -> BatchSttProvider:
    return cast(BatchSttProvider, _build("stt_batch", get_settings().provider_stt_batch))


def get_streaming_stt() -> StreamingSttProvider:
    return cast(StreamingSttProvider, _build("stt_stream", get_settings().provider_stt_stream))


def get_llm() -> LlmProvider:
    return cast(LlmProvider, _build("llm", get_settings().provider_llm))


def get_embedding() -> EmbeddingProvider:
    return cast(EmbeddingProvider, _build("embedding", get_settings().provider_embedding))


def get_tts() -> TtsProvider:
    return cast(TtsProvider, _build("tts", get_settings().provider_tts))


def _require_key(env_choice: str, key_env: str, value: str) -> None:
    if not value:
        raise ValueError(f"{env_choice} needs {key_env}")


def _deepgram() -> DeepgramBatchStt:
    settings = get_settings()
    _require_key("PROVIDER_STT_BATCH=deepgram", "DEEPGRAM_API_KEY", settings.deepgram_api_key)
    return DeepgramBatchStt(settings)


def _anthropic() -> AnthropicLlm:
    settings = get_settings()
    _require_key("PROVIDER_LLM=anthropic", "ANTHROPIC_API_KEY", settings.anthropic_api_key)
    return AnthropicLlm(settings)


def _openai() -> OpenAiEmbedding:
    settings = get_settings()
    _require_key("PROVIDER_EMBEDDING=openai", "OPENAI_API_KEY", settings.openai_api_key)
    return OpenAiEmbedding(settings)


register_provider("stt_batch", "deepgram", _deepgram)
register_provider("llm", "anthropic", _anthropic)
register_provider("embedding", "openai", _openai)
