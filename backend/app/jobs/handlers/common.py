"""Helpers shared by the pipeline job handlers."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import update

from app.db.models.org import Meeting
from app.jobs.registry import JobContext, NonRetryableJobError
from app.providers.base import ProviderError


async def mark_incomplete(ctx: JobContext, message: str) -> None:
    """Flag the meeting as failed; its stage stays so a retry resumes there."""
    async with ctx.session_factory() as session:
        await session.execute(
            update(Meeting)
            .where(Meeting.id == ctx.meeting_id)
            .values(status="incomplete", error=message)
        )


@asynccontextmanager
async def fail_meeting_on_error(ctx: JobContext, message: str) -> AsyncIterator[None]:
    """Mark the meeting incomplete when the job cannot succeed any more.

    A non-retryable provider error fails at once; any other error only on the last attempt.
    Errors are re-raised so the queue records them (and retries when it can).
    """
    try:
        yield
    except NonRetryableJobError:
        raise
    except ProviderError as exc:
        if not exc.retryable:
            await mark_incomplete(ctx, message)
            raise NonRetryableJobError(str(exc)) from exc
        if ctx.is_last_attempt:
            await mark_incomplete(ctx, message)
        raise
    except Exception:
        if ctx.is_last_attempt:
            await mark_incomplete(ctx, message)
        raise
