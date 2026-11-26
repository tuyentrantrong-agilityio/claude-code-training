"""Anthropic Messages API adapter over plain httpx (complete and SSE streaming)."""

import json
import re
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.core.settings import Settings, get_settings
from app.providers._http import error_for_status, error_for_transport, log_ok
from app.providers.base import ProviderError
from app.providers.types import ChatMessage, LlmResult, TokenUsage

MESSAGES_URL = "https://api.anthropic.com/v1/messages"
API_VERSION = "2023-06-01"
JSON_INSTRUCTION = "Respond with a single JSON object only, no prose."
RETRYABLE_ERROR_TYPES = frozenset(
    {"overloaded_error", "api_error", "rate_limit_error", "timeout_error"}
)
_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*\n?(.*?)\n?\s*```\s*$", re.DOTALL | re.IGNORECASE)


def strip_json_fence(text: str) -> str:
    match = _FENCE_RE.match(text)
    return match.group(1).strip() if match else text


def build_payload(
    model: str, messages: list[ChatMessage], max_tokens: int, json_mode: bool
) -> dict[str, Any]:
    system = [m.content for m in messages if m.role == "system"]
    if json_mode:
        system.append(JSON_INSTRUCTION)
    payload: dict[str, Any] = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [
            {"role": m.role, "content": m.content} for m in messages if m.role != "system"
        ],
    }
    if system:
        payload["system"] = "\n\n".join(system)
    return payload


def _stream_error(event: dict[str, Any]) -> ProviderError:
    error = event.get("error") or {}
    kind = str(error.get("type", "unknown"))
    return ProviderError(
        f"anthropic: stream error ({kind})", retryable=kind in RETRYABLE_ERROR_TYPES
    )


class AnthropicLlm:
    name = "anthropic"

    def __init__(
        self, settings: Settings | None = None, client: httpx.AsyncClient | None = None
    ) -> None:
        self._settings = settings or get_settings()
        self._client = client
        self.last_usage: TokenUsage | None = None

    def _headers(self) -> dict[str, str]:
        return {
            "x-api-key": self._settings.anthropic_api_key,
            "anthropic-version": API_VERSION,
            "content-type": "application/json",
        }

    def _timeout(self) -> httpx.Timeout:
        return httpx.Timeout(self._settings.provider_timeout_seconds)

    async def complete(
        self, messages: list[ChatMessage], *, max_tokens: int, json_mode: bool = False
    ) -> LlmResult:
        payload = build_payload(self._settings.anthropic_model, messages, max_tokens, json_mode)
        owned = self._client is None
        client = self._client or httpx.AsyncClient(timeout=self._timeout())
        try:
            response = await client.post(MESSAGES_URL, headers=self._headers(), json=payload)
        except httpx.HTTPError as exc:
            raise error_for_transport(self.name, exc) from exc
        finally:
            if owned:
                await client.aclose()
        if response.status_code >= 400:
            raise error_for_status(self.name, response.status_code, response.headers)
        log_ok(self.name, response.status_code, response.headers)
        try:
            data = response.json()
            text = "".join(b.get("text", "") for b in data["content"] if b.get("type") == "text")
            usage = data["usage"]
            result = LlmResult(
                text=strip_json_fence(text) if json_mode else text,
                input_tokens=int(usage["input_tokens"]),
                output_tokens=int(usage["output_tokens"]),
            )
        except (ValueError, TypeError, KeyError, AttributeError) as exc:
            raise ProviderError("anthropic: unexpected response format") from exc
        return result

    async def stream(self, messages: list[ChatMessage], *, max_tokens: int) -> AsyncIterator[str]:
        self.last_usage = None
        payload = build_payload(self._settings.anthropic_model, messages, max_tokens, False)
        payload["stream"] = True
        owned = self._client is None
        client = self._client or httpx.AsyncClient(timeout=self._timeout())
        tokens_in = tokens_out = 0
        try:
            async with client.stream(
                "POST", MESSAGES_URL, headers=self._headers(), json=payload
            ) as response:
                if response.status_code >= 400:
                    raise error_for_status(self.name, response.status_code, response.headers)
                log_ok(self.name, response.status_code, response.headers)
                async for line in response.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    try:
                        event = json.loads(line[5:].strip())
                    except ValueError as exc:
                        raise ProviderError("anthropic: bad stream event") from exc
                    kind = event.get("type")
                    if kind == "error":
                        raise _stream_error(event)
                    if kind == "message_start":
                        usage = (event.get("message") or {}).get("usage") or {}
                        tokens_in = int(usage.get("input_tokens", tokens_in))
                        tokens_out = int(usage.get("output_tokens", tokens_out))
                    elif kind == "content_block_delta":
                        delta = event.get("delta") or {}
                        if delta.get("type") == "text_delta" and delta.get("text"):
                            yield str(delta["text"])
                    elif kind == "message_delta":
                        usage = event.get("usage") or {}
                        tokens_in = int(usage.get("input_tokens", tokens_in))
                        tokens_out = int(usage.get("output_tokens", tokens_out))
                    elif kind == "message_stop":
                        break
        except httpx.HTTPError as exc:
            raise error_for_transport(self.name, exc) from exc
        finally:
            if owned:
                await client.aclose()
        self.last_usage = TokenUsage(tokens_in, tokens_out)
