"""OpenAI embeddings adapter over plain httpx."""

from typing import Any

import httpx

from app.core.settings import Settings, get_settings
from app.providers._http import error_for_status, error_for_transport, log_ok
from app.providers.base import ProviderError
from app.providers.types import Embedding, EmbeddingResult

EMBEDDINGS_URL = "https://api.openai.com/v1/embeddings"
MAX_BATCH = 256


class OpenAiEmbedding:
    name = "openai"

    def __init__(
        self, settings: Settings | None = None, client: httpx.AsyncClient | None = None
    ) -> None:
        self._settings = settings or get_settings()
        self._client = client
        self.dimensions = self._settings.embedding_dimensions

    async def _batch(
        self, client: httpx.AsyncClient, texts: list[str]
    ) -> tuple[list[Embedding], int]:
        payload: dict[str, Any] = {
            "model": self._settings.openai_embedding_model,
            "input": texts,
            "dimensions": self.dimensions,
            "encoding_format": "float",
        }
        headers = {"Authorization": f"Bearer {self._settings.openai_api_key}"}
        try:
            response = await client.post(EMBEDDINGS_URL, headers=headers, json=payload)
        except httpx.HTTPError as exc:
            raise error_for_transport(self.name, exc) from exc
        if response.status_code >= 400:
            raise error_for_status(self.name, response.status_code, response.headers)
        log_ok(self.name, response.status_code, response.headers)
        try:
            body = response.json()
            rows = sorted(body["data"], key=lambda row: row["index"])
            vectors = [[float(v) for v in row["embedding"]] for row in rows]
            tokens = int(body["usage"]["prompt_tokens"])
        except (ValueError, TypeError, KeyError, AttributeError) as exc:
            raise ProviderError("openai: unexpected response format") from exc
        if len(vectors) != len(texts):
            raise ProviderError("openai: wrong number of embeddings returned")
        return vectors, tokens

    async def embed(self, texts: list[str]) -> EmbeddingResult:
        vectors: list[Embedding] = []
        tokens = 0
        if texts:
            owned = self._client is None
            client = self._client or httpx.AsyncClient(
                timeout=httpx.Timeout(self._settings.provider_timeout_seconds)
            )
            try:
                for start in range(0, len(texts), MAX_BATCH):
                    got, used = await self._batch(client, texts[start : start + MAX_BATCH])
                    vectors.extend(got)
                    tokens += used
            finally:
                if owned:
                    await client.aclose()
        return EmbeddingResult(vectors=vectors, input_tokens=tokens, dimensions=self.dimensions)
