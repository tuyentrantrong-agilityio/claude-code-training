"""Index job: chunk the transcript, embed the chunks and make the meeting ready.

Chunks are replaced in one transaction, so a retried job never duplicates rows. A meeting
without speech gets no chunks and is still ready.
"""

import logging

from sqlalchemy import select

from app.db.models.org import Meeting, MeetingParticipant, TranscriptSegment
from app.jobs.handlers.common import fail_meeting_on_error
from app.jobs.registry import JobContext, NonRetryableJobError, handler
from app.providers.metering import MeteredEmbedding
from app.providers.registry import get_embedding
from app.services.indexing import IndexLine, build_chunks, replace_chunks
from app.services.recap import UNKNOWN_SPEAKER

logger = logging.getLogger(__name__)

INDEX_ERROR = "Could not index the meeting for search."


@handler("index")
async def index(ctx: JobContext) -> None:
    meeting_id = ctx.meeting_id
    if meeting_id is None:
        raise NonRetryableJobError("index job without a meeting")
    async with fail_meeting_on_error(ctx, INDEX_ERROR), ctx.session_factory() as session:
        meeting = await session.scalar(
            select(Meeting).where(Meeting.id == meeting_id, Meeting.deleted_at.is_(None))
        )
        if meeting is None:
            logger.warning("index: meeting %s not found (deleted?)", meeting_id)
            return
        rows = (
            await session.execute(
                select(
                    TranscriptSegment.start_ms,
                    TranscriptSegment.end_ms,
                    TranscriptSegment.text,
                    MeetingParticipant.display_name,
                    MeetingParticipant.speaker_label,
                )
                .join(
                    MeetingParticipant,
                    MeetingParticipant.id == TranscriptSegment.participant_id,
                    isouter=True,
                )
                .where(TranscriptSegment.meeting_id == meeting_id)
                .order_by(TranscriptSegment.seq)
            )
        ).all()
        lines = [
            IndexLine(s, e, name or label or UNKNOWN_SPEAKER, t) for s, e, t, name, label in rows
        ]
        chunks = build_chunks(lines)
        vectors: list[list[float]] = []
        if chunks:
            embedder = MeteredEmbedding(get_embedding(), session, meeting_id)
            vectors = (await embedder.embed([c.text for c in chunks])).vectors
        await replace_chunks(session, meeting_id, chunks, vectors)
        meeting.stage, meeting.status, meeting.error = None, "ready", None
        await session.flush()
