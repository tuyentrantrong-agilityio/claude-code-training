"""Home screen data: open follow-ups of the user and the latest ready meetings."""

import uuid

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.org import Meeting
from app.services import meetings as meetings_svc
from app.services import reports

NEEDS_YOU_LIMIT = 4
RECENT_LIMIT = 3


class HomeOut(BaseModel):
    needs_you: list[reports.FollowUpItemOut]
    recent_meetings: list[meetings_svc.MeetingOut]
    has_any_meeting: bool


async def get_home(session: AsyncSession, user_id: uuid.UUID) -> HomeOut:
    follow_ups = await reports.list_follow_ups(session, user_id, "me", "open", NEEDS_YOU_LIMIT)
    meetings = list(
        await session.scalars(
            select(Meeting)
            .where(Meeting.status == "ready", Meeting.deleted_at.is_(None))
            .order_by(meetings_svc.sort_key().desc(), Meeting.id.desc())
            .limit(RECENT_LIMIT)
        )
    )
    people = await meetings_svc.participants_for(session, [m.id for m in meetings])
    any_meeting = await session.scalar(
        select(select(Meeting.id).where(Meeting.deleted_at.is_(None)).exists())
    )
    return HomeOut(
        needs_you=follow_ups.items,
        recent_meetings=[meetings_svc.to_summary(m, people[m.id]) for m in meetings],
        has_any_meeting=bool(any_meeting),
    )
