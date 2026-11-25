import uuid
from contextlib import AbstractAsyncContextManager

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.jobs.queue import MAX_ERROR_LENGTH, backoff_seconds, truncate_error
from app.jobs.registry import HANDLERS, JobContext, UnknownJobKindError, dispatch, handler


def _ctx() -> JobContext:
    def no_session() -> AbstractAsyncContextManager[AsyncSession]:
        raise AssertionError("session not expected in unit tests")

    return JobContext("org_000000000000", uuid.uuid4(), None, no_session)


def test_backoff_grows_exponentially() -> None:
    assert [backoff_seconds(n) for n in (1, 2, 3, 4)] == [5, 10, 20, 40]


def test_backoff_is_capped() -> None:
    assert backoff_seconds(20) == 600
    assert backoff_seconds(0) == 5


def test_truncate_error() -> None:
    assert truncate_error("short") == "short"
    assert len(truncate_error("x" * 5000)) == MAX_ERROR_LENGTH


async def test_unknown_kind_raises_clear_error() -> None:
    with pytest.raises(UnknownJobKindError, match="no handler registered for job kind 'index'"):
        await dispatch("index", _ctx())


async def test_dispatch_runs_registered_handler() -> None:
    seen: list[uuid.UUID] = []

    @handler("unit-test-kind")
    async def _h(ctx: JobContext) -> None:
        seen.append(ctx.job_id)

    try:
        ctx = _ctx()
        await dispatch("unit-test-kind", ctx)
        assert seen == [ctx.job_id]
    finally:
        HANDLERS.pop("unit-test-kind", None)
