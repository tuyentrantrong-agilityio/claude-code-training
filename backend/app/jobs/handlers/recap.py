"""Recap job: summary, follow-ups, key points, chapters, highlights and questions.

When the recap is saved the meeting moves to the "filing" stage and an index job is queued.

A reply that is not valid JSON is retried once (the model may answer differently); a second
bad reply marks the meeting incomplete.
"""

import logging

from sqlalchemy import select

from app.core.settings import get_settings
from app.db.models.org import Meeting, MeetingParticipant, TranscriptSegment
from app.db.models.public import Membership, Organization, User
from app.jobs import queue
from app.jobs.handlers.common import fail_meeting_on_error, mark_incomplete
from app.jobs.registry import JobContext, NonRetryableJobError, handler
from app.providers.metering import MeteredLlm
from app.providers.registry import get_llm
from app.services.recap import (
    NO_SPEECH_SUMMARY,
    UNKNOWN_SPEAKER,
    Member,
    PromptLine,
    Recap,
    RecapParseError,
    build_messages,
    parse_recap,
    replace_recap,
    validate_recap,
)

logger = logging.getLogger(__name__)

RECAP_ERROR = "Could not generate the recap."
PARSE_ATTEMPTS = 2


@handler("recap")
async def recap(ctx: JobContext) -> None:
    meeting_id = ctx.meeting_id
    if meeting_id is None:
        raise NonRetryableJobError("recap job without a meeting")
    parse_error: RecapParseError | None = None
    async with fail_meeting_on_error(ctx, RECAP_ERROR), ctx.session_factory() as session:
        meeting = await session.scalar(
            select(Meeting).where(Meeting.id == meeting_id, Meeting.deleted_at.is_(None))
        )
        if meeting is None:
            logger.warning("recap: meeting %s not found (deleted?)", meeting_id)
            return
        rows = (
            await session.execute(
                select(
                    TranscriptSegment.start_ms,
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
        lines = [PromptLine(s, name or label or UNKNOWN_SPEAKER, t) for s, t, name, label in rows]
        members = [
            Member(uid, name, email)
            for uid, name, email in await session.execute(
                select(User.id, User.name, User.email)
                .join(Membership, Membership.user_id == User.id)
                .join(Organization, Organization.id == Membership.organization_id)
                .where(Organization.schema_name == ctx.schema_name)
            )
        ]
        if not lines:
            await replace_recap(session, meeting, Recap(summary=NO_SPEECH_SUMMARY), members)
            await queue.enqueue(session, "index", meeting_id)
            return
        llm = MeteredLlm(get_llm(), session, meeting_id)
        result = await llm.complete(
            build_messages(lines, meeting.language),
            max_tokens=get_settings().recap_max_tokens,
            json_mode=True,
        )
        try:
            parsed = parse_recap(result.text)
        except RecapParseError as exc:
            parse_error = exc  # leave the block normally so the usage events are kept
        else:
            starts = [line.start_ms for line in lines]
            checked = validate_recap(parsed, starts, meeting.duration_ms)
            await replace_recap(session, meeting, checked, members)
            await queue.enqueue(session, "index", meeting_id)
    if parse_error is not None:
        if ctx.attempts >= min(PARSE_ATTEMPTS, ctx.max_attempts):
            await mark_incomplete(ctx, RECAP_ERROR)
            raise NonRetryableJobError(str(parse_error)) from parse_error
        raise parse_error
