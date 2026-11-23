"""Background job worker: python -m app.jobs.worker"""

import asyncio
import contextlib
import logging
import signal
import socket
import uuid
from datetime import timedelta
from functools import partial

from sqlalchemy import select

from app.core.settings import get_settings
from app.db.models.public import Organization
from app.db.session import get_engine, get_sessionmaker, tenant_session
from app.jobs import queue
from app.jobs.registry import JobContext, UnknownJobKindError, dispatch

logger = logging.getLogger(__name__)


class Worker:
    def __init__(
        self,
        worker_id: str | None = None,
        max_attempts: int | None = None,
        stale_after: timedelta | None = None,
    ) -> None:
        settings = get_settings()
        self.worker_id = worker_id or f"{socket.gethostname()}-{uuid.uuid4().hex[:8]}"
        self.max_attempts = max_attempts or settings.job_max_attempts
        self.stale_after = stale_after or timedelta(seconds=settings.job_stale_after_seconds)
        self._stop = asyncio.Event()

    def stop(self) -> None:
        self._stop.set()

    async def _schemas(self) -> list[str]:
        async with get_sessionmaker()() as session:
            rows = await session.scalars(
                select(Organization.schema_name).order_by(Organization.name)
            )
            return list(rows)

    async def run_once(self) -> int:
        """Process at most one job per org schema; return how many were processed."""
        processed = 0
        for schema in await self._schemas():
            try:
                if await self._process_schema(schema):
                    processed += 1
            except Exception:
                logger.exception("worker error in schema %s", schema)
        return processed

    async def recover_stale(self) -> int:
        total = 0
        for schema in await self._schemas():
            try:
                async with tenant_session(schema) as session:
                    total += await queue.requeue_stale(session, self.stale_after)
            except Exception:
                logger.exception("stale recovery failed in schema %s", schema)
        if total:
            logger.warning("requeued %d stale job(s)", total)
        return total

    async def _process_schema(self, schema: str) -> bool:
        async with tenant_session(schema) as session:
            job = await queue.claim_next(session, self.worker_id)
        if job is None:
            return False
        job_id, kind = job.id, job.kind
        ctx = JobContext(
            schema_name=schema,
            job_id=job_id,
            meeting_id=job.meeting_id,
            session_factory=partial(tenant_session, schema),
        )
        max_attempts = self.max_attempts
        try:
            await dispatch(kind, ctx)
        except UnknownJobKindError as exc:
            logger.error("job %s kind=%s schema=%s: %s", job_id, kind, schema, exc)
            error, max_attempts = str(exc), 0
        except Exception as exc:
            logger.exception("job %s kind=%s schema=%s failed", job_id, kind, schema)
            error = f"{type(exc).__name__}: {exc}"
        else:
            async with tenant_session(schema) as session:
                await queue.mark_succeeded(session, job_id)
            logger.info("job %s kind=%s schema=%s succeeded", job_id, kind, schema)
            return True
        async with tenant_session(schema) as session:
            await queue.mark_failed(session, job_id, error, max_attempts)
        return True

    async def run_forever(self, poll_interval: float | None = None) -> None:
        interval = (
            get_settings().worker_poll_interval_seconds if poll_interval is None else poll_interval
        )
        logger.info("worker %s started", self.worker_id)
        while not self._stop.is_set():
            try:
                await self.recover_stale()
                busy = await self.run_once()
            except Exception:
                logger.exception("worker loop error")
                busy = 0
            if busy:
                continue
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(self._stop.wait(), timeout=interval)
        logger.info("worker %s stopped", self.worker_id)


async def _main() -> None:
    worker = Worker()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, worker.stop)
    try:
        await worker.run_forever()
    finally:
        await get_engine().dispose()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    asyncio.run(_main())


if __name__ == "__main__":
    main()
