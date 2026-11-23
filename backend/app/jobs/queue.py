"""Job queue primitives. Every function runs inside an org tenant session."""

import uuid
from datetime import datetime, timedelta

from sqlalchemy import func, select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.org import Job

BACKOFF_BASE_SECONDS = 5.0
BACKOFF_CAP_SECONDS = 600.0
MAX_ERROR_LENGTH = 2000


def backoff_seconds(attempts: int) -> float:
    """Delay before the next try: base * 2**(attempts-1), capped."""
    exponent = max(attempts, 1) - 1
    return float(min(BACKOFF_BASE_SECONDS * 2**exponent, BACKOFF_CAP_SECONDS))


def truncate_error(error: str) -> str:
    return error[:MAX_ERROR_LENGTH]


async def enqueue(
    session: AsyncSession,
    kind: str,
    meeting_id: uuid.UUID | None = None,
    run_after: datetime | None = None,
) -> uuid.UUID:
    """Insert a queued job, or return the id of the active job with the same key.

    The partial unique index only covers rows with a meeting_id, so jobs without
    one are never deduplicated.
    """
    values: dict[str, object] = {"kind": kind, "meeting_id": meeting_id}
    if run_after is not None:
        values["run_after"] = run_after
    stmt = (
        insert(Job)
        .values(**values)
        .on_conflict_do_nothing(
            index_elements=[Job.meeting_id, Job.kind],
            index_where=text("state IN ('queued', 'running')"),
        )
        .returning(Job.id)
    )
    while True:
        job_id = await session.scalar(stmt)
        if job_id is not None:
            return job_id
        # Conflict: look up the active job. It may finish in between, so retry.
        existing = await session.scalar(
            select(Job.id).where(
                Job.meeting_id == meeting_id,
                Job.kind == kind,
                Job.state.in_(("queued", "running")),
            )
        )
        if existing is not None:
            return existing


async def claim_next(session: AsyncSession, worker_id: str) -> Job | None:
    """Lock the oldest due job and mark it running; None when nothing is due."""
    job = await session.scalar(
        select(Job)
        .where(Job.state == "queued", Job.run_after <= func.now())
        .order_by(Job.run_after)
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    if job is None:
        return None
    await session.execute(
        update(Job)
        .where(Job.id == job.id)
        .values(
            state="running",
            locked_by=worker_id,
            locked_at=func.now(),
            attempts=Job.attempts + 1,
        )
    )
    await session.refresh(job)
    return job


async def mark_succeeded(session: AsyncSession, job_id: uuid.UUID) -> None:
    await session.execute(
        update(Job)
        .where(Job.id == job_id)
        .values(state="succeeded", locked_by=None, locked_at=None)
    )


async def mark_failed(
    session: AsyncSession, job_id: uuid.UUID, error: str, max_attempts: int
) -> None:
    """Retry with backoff while attempts remain, otherwise fail for good."""
    attempts = await session.scalar(select(Job.attempts).where(Job.id == job_id))
    if attempts is None:
        return
    values: dict[str, object] = {
        "last_error": truncate_error(error),
        "locked_by": None,
        "locked_at": None,
    }
    if attempts < max_attempts:
        values["state"] = "queued"
        values["run_after"] = func.now() + timedelta(seconds=backoff_seconds(attempts))
    else:
        values["state"] = "failed"
    await session.execute(update(Job).where(Job.id == job_id).values(**values))


async def requeue_stale(session: AsyncSession, older_than: timedelta) -> int:
    """Return jobs stuck in running (crashed worker) to the queue."""
    result = await session.execute(
        update(Job)
        .where(Job.state == "running", Job.locked_at < func.now() - older_than)
        .values(state="queued", locked_by=None, locked_at=None)
    )
    return int(result.rowcount)  # type: ignore[attr-defined]
