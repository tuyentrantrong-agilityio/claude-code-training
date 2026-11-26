"""PLACEHOLDER transcribe handler.

The real transcription (speech to text, speakers, recap) arrives in P-04. Until then this
only marks the meeting ready so the upload flow can be tried end to end.
"""

import logging

from sqlalchemy import update

from app.db.models.org import Meeting
from app.jobs.registry import JobContext, handler

logger = logging.getLogger(__name__)


@handler("transcribe")
async def transcribe(ctx: JobContext) -> None:
    if ctx.meeting_id is None:
        return
    async with ctx.session_factory() as session:
        await session.execute(
            update(Meeting)
            .where(Meeting.id == ctx.meeting_id)
            .values(status="ready", stage=None, error=None)
        )
    logger.info("placeholder transcribe: meeting %s marked ready", ctx.meeting_id)
