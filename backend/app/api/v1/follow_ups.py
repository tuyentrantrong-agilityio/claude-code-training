import uuid
from typing import Literal

from fastapi import APIRouter

from app.api.deps import CsrfSession, Current
from app.db.session import tenant_session
from app.services import reports

router = APIRouter(prefix="/follow-ups", tags=["follow-ups"])


@router.get("")
async def list_follow_ups(
    current: Current,
    owner: Literal["me", "all"] = "all",
    state: Literal["open", "done"] | None = None,
) -> reports.FollowUpsOut:
    async with tenant_session(current.schema_name) as session:
        return await reports.list_follow_ups(session, current.user.id, owner, state)


@router.get("/count")
async def count_follow_ups(current: Current) -> reports.FollowUpCountOut:
    async with tenant_session(current.schema_name) as session:
        return await reports.count_open_mine(session, current.user.id)


@router.patch("/{follow_up_id}")
async def patch_follow_up(
    follow_up_id: uuid.UUID, body: reports.FollowUpPatch, current: CsrfSession
) -> reports.FollowUpItemOut:
    async with tenant_session(current.schema_name) as session:
        return await reports.set_follow_up_state(session, follow_up_id, body.state)
