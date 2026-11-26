"""Shared HTTP helpers for the real provider adapters.

Nothing here logs keys, audio, prompts or response bodies: only status codes and request ids.
"""

import logging

import httpx

from app.providers.base import ProviderError, ProviderTimeout

logger = logging.getLogger(__name__)

REQUEST_ID_HEADERS = ("request-id", "x-request-id", "dg-request-id")


def request_id(headers: httpx.Headers) -> str:
    for name in REQUEST_ID_HEADERS:
        value = headers.get(name)
        if value:
            return str(value)
    return "-"


def error_for_status(provider: str, status: int, headers: httpx.Headers) -> ProviderError:
    """Map a non-2xx status to a ProviderError with the right retryable flag."""
    logger.warning("%s: http %s request_id=%s", provider, status, request_id(headers))
    if status in (401, 403):
        return ProviderError(f"{provider}: invalid credentials (http {status})", retryable=False)
    if status in (408, 429) or status >= 500:
        return ProviderError(f"{provider}: http {status}", retryable=True)
    return ProviderError(f"{provider}: request rejected (http {status})", retryable=False)


def error_for_transport(provider: str, exc: httpx.HTTPError) -> ProviderError:
    """Map a network or timeout failure; both are retryable."""
    logger.warning("%s: transport error %s", provider, type(exc).__name__)
    if isinstance(exc, httpx.TimeoutException):
        return ProviderTimeout(f"{provider}: request timed out")
    return ProviderError(f"{provider}: network error ({type(exc).__name__})", retryable=True)


def log_ok(provider: str, status: int, headers: httpx.Headers) -> None:
    logger.info("%s: http %s request_id=%s", provider, status, request_id(headers))
