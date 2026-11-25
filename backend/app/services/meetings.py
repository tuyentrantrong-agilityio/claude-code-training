"""Meeting queries and serialization shared by the meetings routes."""

import base64
import json
import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel
from sqlalchemy import ColumnElement, func, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.db.models.org import Job, Meeting, MeetingParticipant

STATUSES = ("processing", "ready", "incomplete")
PREVIEW_LENGTH = 160
# Stage that failed -> job that runs it again.
STAGE_JOB = {
    "uploading": "decode",
    "transcribing": "transcribe",
    "summarizing": "recap",
    "filing": "index",
}


class ParticipantOut(BaseModel):
    id: str
    display_name: str | None


class MeetingOut(BaseModel):
    id: str
    title: str
    status: str
    stage: str | None
    error: str | None
    source: str
    platform: str
    language: str
    started_at: datetime | None
    duration_ms: int | None
    summary_preview: str | None
    participants: list[ParticipantOut]
    folder: None = None


class MeetingDetailOut(MeetingOut):
    summary: str | None
    summary_edited_at: datetime | None


def meeting_not_found() -> AppError:
    return AppError("meeting_not_found", "Meeting not found.", status_code=404)


async def get_meeting(session: AsyncSession, meeting_id: uuid.UUID) -> Meeting:
    meeting = await session.scalar(
        select(Meeting).where(Meeting.id == meeting_id, Meeting.deleted_at.is_(None))
    )
    if meeting is None:
        raise meeting_not_found()
    return meeting


async def participants_for(
    session: AsyncSession, meeting_ids: list[uuid.UUID]
) -> dict[uuid.UUID, list[ParticipantOut]]:
    result: dict[uuid.UUID, list[ParticipantOut]] = {mid: [] for mid in meeting_ids}
    if not meeting_ids:
        return result
    rows = await session.scalars(
        select(MeetingParticipant)
        .where(MeetingParticipant.meeting_id.in_(meeting_ids))
        .order_by(MeetingParticipant.created_at, MeetingParticipant.id)
    )
    for row in rows:
        result[row.meeting_id].append(
            ParticipantOut(id=str(row.id), display_name=row.display_name or row.speaker_label)
        )
    return result


def _fields(meeting: Meeting, participants: list[ParticipantOut]) -> dict[str, Any]:
    summary = meeting.summary
    preview = None
    if summary:
        preview = summary if len(summary) <= PREVIEW_LENGTH else summary[:PREVIEW_LENGTH] + "..."
    return {
        "id": str(meeting.id),
        "title": meeting.title,
        "status": meeting.status,
        "stage": meeting.stage,
        "error": meeting.error,
        "source": meeting.source,
        "platform": meeting.platform,
        "language": meeting.language,
        "started_at": meeting.started_at,
        "duration_ms": meeting.duration_ms,
        "summary_preview": preview,
        "participants": participants,
    }


def to_summary(meeting: Meeting, participants: list[ParticipantOut]) -> MeetingOut:
    return MeetingOut(**_fields(meeting, participants))


def to_detail(meeting: Meeting, participants: list[ParticipantOut]) -> MeetingDetailOut:
    return MeetingDetailOut(
        **_fields(meeting, participants),
        summary=meeting.summary,
        summary_edited_at=meeting.summary_edited_at,
    )


def sort_key() -> ColumnElement[datetime]:
    return func.coalesce(Meeting.started_at, Meeting.created_at)


def encode_cursor(when: datetime, meeting_id: uuid.UUID) -> str:
    raw = json.dumps({"t": when.isoformat(), "id": str(meeting_id)})
    return base64.urlsafe_b64encode(raw.encode()).decode()


def decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    try:
        data = json.loads(base64.urlsafe_b64decode(cursor.encode()))
        when = datetime.fromisoformat(data["t"])
        if when.tzinfo is None:
            when = when.replace(tzinfo=UTC)
        return when, uuid.UUID(data["id"])
    except (ValueError, KeyError, TypeError) as exc:
        raise AppError("validation_error", "Invalid cursor", status_code=400) from exc


async def list_meetings(
    session: AsyncSession, status: str | None, q: str | None, limit: int, cursor: str | None
) -> dict[str, Any]:
    base: list[ColumnElement[bool]] = [Meeting.deleted_at.is_(None)]
    if q:
        base.append(Meeting.title.icontains(q, autoescape=True))
    counts = dict.fromkeys(STATUSES, 0)
    count_rows = await session.execute(
        select(Meeting.status, func.count()).where(*base).group_by(Meeting.status)
    )
    for name, total in count_rows:
        counts[name] = total
    stmt = select(Meeting).where(*base)
    if status:
        stmt = stmt.where(Meeting.status == status)
    if cursor:
        when, last_id = decode_cursor(cursor)
        stmt = stmt.where(tuple_(sort_key(), Meeting.id) < tuple_(when, last_id))
    stmt = stmt.order_by(sort_key().desc(), Meeting.id.desc()).limit(limit + 1)
    rows = list((await session.scalars(stmt)).all())
    page = rows[:limit]
    next_cursor = None
    if len(rows) > limit:
        last = page[-1]
        next_cursor = encode_cursor(last.started_at or last.created_at, last.id)
    people = await participants_for(session, [m.id for m in page])
    return {
        "items": [to_summary(m, people[m.id]) for m in page],
        "next_cursor": next_cursor,
        "meta": {"counts": counts},
    }


async def has_active_job(session: AsyncSession, meeting_id: uuid.UUID) -> bool:
    found = await session.scalar(
        select(Job.id)
        .where(Job.meeting_id == meeting_id, Job.state.in_(("queued", "running")))
        .limit(1)
    )
    return found is not None
