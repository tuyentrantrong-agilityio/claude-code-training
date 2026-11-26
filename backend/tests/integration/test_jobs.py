import uuid
from collections.abc import Iterator
from datetime import timedelta

import pytest
from sqlalchemy import delete, func, select, update

from app.db.models.org import Job, Meeting
from app.db.models.public import Organization
from app.db.session import get_sessionmaker, tenant_session
from app.jobs import queue
from app.jobs.registry import HANDLERS, JobContext, handler
from app.jobs.worker import Worker


async def _meeting(schema: str) -> uuid.UUID:
    async with tenant_session(schema) as session:
        meeting = Meeting(
            title="m", source="upload", platform="file", language="en", status="processing"
        )
        session.add(meeting)
        await session.flush()
        return meeting.id


async def _get(schema: str, job_id: uuid.UUID) -> Job:
    async with tenant_session(schema) as session:
        return (await session.execute(select(Job).where(Job.id == job_id))).scalar_one()


async def _make_due(schema: str, job_id: uuid.UUID) -> None:
    async with tenant_session(schema) as session:
        await session.execute(
            update(Job).where(Job.id == job_id).values(run_after=func.now() - timedelta(seconds=1))
        )


@pytest.fixture(autouse=True)
async def clean_jobs() -> None:
    # The worker scans every org, so drop jobs left behind by earlier tests.
    async with get_sessionmaker()() as session:
        schemas = list(await session.scalars(select(Organization.schema_name)))
    for schema in schemas:
        async with tenant_session(schema) as session:
            await session.execute(delete(Job))


@pytest.fixture
def failing_handler() -> Iterator[list[int]]:
    calls: list[int] = []
    original = HANDLERS.get("index")  # the real index handler must come back afterwards

    @handler("index")
    async def _boom(ctx: JobContext) -> None:
        calls.append(1)
        raise RuntimeError("boom")

    yield calls
    if original is None:
        HANDLERS.pop("index", None)
    else:
        HANDLERS["index"] = original


async def test_enqueue_dedups_active_job(two_orgs: tuple[str, str]) -> None:
    schema = two_orgs[0]
    meeting_id = await _meeting(schema)
    async with tenant_session(schema) as session:
        first = await queue.enqueue(session, "cleanup", meeting_id)
    async with tenant_session(schema) as session:
        second = await queue.enqueue(session, "cleanup", meeting_id)
        other = await queue.enqueue(session, "decode", meeting_id)
    assert first == second
    assert other != first


async def test_enqueue_allows_new_job_after_completion(two_orgs: tuple[str, str]) -> None:
    schema = two_orgs[0]
    meeting_id = await _meeting(schema)
    async with tenant_session(schema) as session:
        first = await queue.enqueue(session, "cleanup", meeting_id)
        await queue.mark_succeeded(session, first)
        second = await queue.enqueue(session, "cleanup", meeting_id)
    assert first != second


async def test_concurrent_claims_never_share_a_job(two_orgs: tuple[str, str]) -> None:
    schema = two_orgs[0]
    async with tenant_session(schema) as session:
        ids = {await queue.enqueue(session, "cleanup") for _ in range(2)}
    async with tenant_session(schema) as s1, tenant_session(schema) as s2:
        job1 = await queue.claim_next(s1, "w1")
        job2 = await queue.claim_next(s2, "w2")
        job3 = await queue.claim_next(s2, "w2")
        assert job1 is not None and job2 is not None
        assert job1.id != job2.id
        assert {job1.id, job2.id} == ids
        assert job3 is None
        assert job1.state == "running" and job1.attempts == 1 and job1.locked_by == "w1"


async def test_claim_skips_future_jobs(two_orgs: tuple[str, str]) -> None:
    schema = two_orgs[0]
    async with tenant_session(schema) as session:
        await queue.enqueue(session, "cleanup", run_after=None)
        await session.execute(update(Job).values(run_after=func.now() + timedelta(hours=1)))
    async with tenant_session(schema) as session:
        assert await queue.claim_next(session, "w") is None


async def test_worker_success_path(two_orgs: tuple[str, str]) -> None:
    schema = two_orgs[0]
    async with tenant_session(schema) as session:
        job_id = await queue.enqueue(session, "cleanup")
    worker = Worker(worker_id="test")
    assert await worker.run_once() == 1
    assert await worker.run_once() == 0
    job = await _get(schema, job_id)
    assert job.state == "succeeded"
    assert job.attempts == 1
    assert job.locked_by is None


async def test_failing_handler_retries_then_fails(
    two_orgs: tuple[str, str], failing_handler: list[int]
) -> None:
    schema = two_orgs[0]
    async with tenant_session(schema) as session:
        job_id = await queue.enqueue(session, "index")
    worker = Worker(worker_id="test", max_attempts=3)

    assert await worker.run_once() == 1
    job = await _get(schema, job_id)
    assert (job.state, job.attempts) == ("queued", 1)
    assert job.last_error == "RuntimeError: boom"
    assert await worker.run_once() == 0  # backoff keeps it out of the queue

    await _make_due(schema, job_id)
    assert await worker.run_once() == 1
    job = await _get(schema, job_id)
    assert (job.state, job.attempts) == ("queued", 2)

    await _make_due(schema, job_id)
    assert await worker.run_once() == 1
    job = await _get(schema, job_id)
    assert (job.state, job.attempts) == ("failed", 3)
    assert len(failing_handler) == 3
    assert await worker.run_once() == 0


async def test_unknown_kind_fails_immediately(
    two_orgs: tuple[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    # Every allowed kind has a handler now, so take the index handler away for this test.
    monkeypatch.delitem(HANDLERS, "index")
    schema = two_orgs[0]
    async with tenant_session(schema) as session:
        job_id = await queue.enqueue(session, "index")
    assert await Worker(worker_id="test").run_once() == 1
    job = await _get(schema, job_id)
    assert job.state == "failed"
    assert job.last_error is not None and "no handler registered" in job.last_error


async def test_long_error_is_truncated(two_orgs: tuple[str, str]) -> None:
    schema = two_orgs[0]
    async with tenant_session(schema) as session:
        job_id = await queue.enqueue(session, "cleanup")
        claimed = await queue.claim_next(session, "w")
        assert claimed is not None
        await queue.mark_failed(session, job_id, "x" * 5000, max_attempts=3)
    job = await _get(schema, job_id)
    assert job.last_error is not None and len(job.last_error) == 2000


async def test_requeue_stale(two_orgs: tuple[str, str]) -> None:
    schema = two_orgs[0]
    async with tenant_session(schema) as session:
        job_id = await queue.enqueue(session, "cleanup")
        await queue.claim_next(session, "dead-worker")
    async with tenant_session(schema) as session:
        assert await queue.requeue_stale(session, timedelta(minutes=10)) == 0
        await session.execute(update(Job).values(locked_at=func.now() - timedelta(minutes=30)))
    async with tenant_session(schema) as session:
        assert await queue.requeue_stale(session, timedelta(minutes=10)) == 1
    job = await _get(schema, job_id)
    assert job.state == "queued" and job.locked_by is None


async def test_jobs_stay_in_their_org(two_orgs: tuple[str, str]) -> None:
    schema_a, schema_b = two_orgs
    async with tenant_session(schema_a) as session:
        job_id = await queue.enqueue(session, "cleanup")
    async with tenant_session(schema_b) as session:
        assert await queue.claim_next(session, "w") is None
    assert (await _get(schema_a, job_id)).state == "queued"
    assert await Worker(worker_id="test").run_once() == 1
    async with tenant_session(schema_b) as session:
        assert await session.scalar(select(func.count()).select_from(Job)) == 0
