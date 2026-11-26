"""Handler registry: job kind -> async handler."""

import logging
import uuid
from collections.abc import Awaitable, Callable
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

SessionFactory = Callable[[], AbstractAsyncContextManager[AsyncSession]]


@dataclass(frozen=True)
class JobContext:
    schema_name: str
    job_id: uuid.UUID
    meeting_id: uuid.UUID | None
    session_factory: SessionFactory
    attempts: int = 1  # includes the current run
    max_attempts: int = 1

    @property
    def is_last_attempt(self) -> bool:
        return self.attempts >= self.max_attempts


Handler = Callable[[JobContext], Awaitable[None]]

HANDLERS: dict[str, Handler] = {}


class UnknownJobKindError(Exception):
    def __init__(self, kind: str) -> None:
        super().__init__(f"no handler registered for job kind {kind!r}")
        self.kind = kind


class NonRetryableJobError(Exception):
    """Raised by a handler when trying again cannot help; the job fails at once."""


def handler(kind: str) -> Callable[[Handler], Handler]:
    def register(fn: Handler) -> Handler:
        HANDLERS[kind] = fn
        return fn

    return register


async def dispatch(kind: str, ctx: JobContext) -> None:
    fn = HANDLERS.get(kind)
    if fn is None:
        raise UnknownJobKindError(kind)
    await fn(ctx)


@handler("cleanup")
async def cleanup(ctx: JobContext) -> None:
    logger.info("cleanup job %s in %s: nothing to do", ctx.job_id, ctx.schema_name)


__all__ = [
    "HANDLERS",
    "Handler",
    "JobContext",
    "NonRetryableJobError",
    "UnknownJobKindError",
    "dispatch",
    "handler",
]
