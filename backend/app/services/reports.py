"""Read side of the pipeline: recap, transcript, people, follow-ups and exports."""

import re
import unicodedata
import uuid
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, field_validator
from sqlalchemy import ColumnElement, Select, and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.db.models.org import (
    FollowUp,
    Meeting,
    MeetingParticipant,
    RecapItem,
    TranscriptSegment,
)

MAX_NAME_LENGTH = 80
MAX_FOLLOW_UPS = 500
MAX_SLUG_LENGTH = 60
UNKNOWN_SPEAKER = "Unknown"


# ---- response shapes ----


class FollowUpOut(BaseModel):
    id: str
    text: str
    owner_name: str | None
    owner_user_id: str | None
    at_ms: int | None
    state: str


class KeyPointOut(BaseModel):
    id: str
    title: str | None
    text: str | None
    at_ms: int | None


class ChapterOut(BaseModel):
    id: str
    title: str | None
    at_ms: int | None


class TextItemOut(BaseModel):
    id: str
    text: str | None
    at_ms: int | None


class RecapOut(BaseModel):
    summary: str | None
    summary_edited_at: datetime | None
    follow_ups: list[FollowUpOut]
    key_points: list[KeyPointOut]
    chapters: list[ChapterOut]
    highlights: list[TextItemOut]
    questions: list[TextItemOut]


class SegmentOut(BaseModel):
    id: str
    seq: int
    start_ms: int
    end_ms: int
    participant_id: str | None
    speaker: str | None
    text: str


class TranscriptOut(BaseModel):
    segments: list[SegmentOut]


class PersonOut(BaseModel):
    participant_id: str
    display_name: str | None
    speaker_label: str | None
    talk_ms: int
    share: float


class PeopleOut(BaseModel):
    people: list[PersonOut]


class ParticipantPatch(BaseModel):
    display_name: str

    @field_validator("display_name")
    @classmethod
    def _name(cls, value: str) -> str:
        value = value.strip()
        if not 1 <= len(value) <= MAX_NAME_LENGTH:
            raise ValueError(f"display_name must be 1 to {MAX_NAME_LENGTH} characters")
        return value


class ParticipantOut(BaseModel):
    participant_id: str
    display_name: str | None
    speaker_label: str | None


class FollowUpItemOut(FollowUpOut):
    meeting_id: str
    meeting_title: str


class FollowUpsOut(BaseModel):
    items: list[FollowUpItemOut]


class FollowUpCountOut(BaseModel):
    open_mine: int


class FollowUpPatch(BaseModel):
    state: Literal["open", "done"]


# ---- formatting ----


def format_mmss(ms: int | None) -> str:
    """mm:ss; minutes keep counting past 59 (a 75 minute mark is 75:00)."""
    seconds = max(ms or 0, 0) // 1000
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


def slugify(title: str) -> str:
    """Lowercase ASCII slug for file names; "meeting" when nothing is left."""
    text = title.replace("\u0111", "d").replace("\u0110", "D")
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:MAX_SLUG_LENGTH].strip("-")
    return slug or "meeting"


def _speaker_name() -> ColumnElement[str]:
    return func.coalesce(MeetingParticipant.display_name, MeetingParticipant.speaker_label)


# ---- queries ----


def _opt(value: uuid.UUID | None) -> str | None:
    return None if value is None else str(value)


def _follow_up_out(row: FollowUp) -> FollowUpOut:
    return FollowUpOut(
        id=str(row.id),
        text=row.text,
        owner_name=row.owner_name,
        owner_user_id=_opt(row.owner_user_id),
        at_ms=row.at_ms,
        state=row.state,
    )


async def get_recap(session: AsyncSession, meeting: Meeting) -> RecapOut:
    follow_ups = await session.scalars(
        select(FollowUp)
        .where(FollowUp.meeting_id == meeting.id)
        .order_by(FollowUp.created_at, FollowUp.id)
    )
    items = (
        await session.scalars(
            select(RecapItem)
            .where(RecapItem.meeting_id == meeting.id)
            .order_by(RecapItem.kind, RecapItem.seq)
        )
    ).all()

    def of_kind(kind: str) -> list[RecapItem]:
        return [i for i in items if i.kind == kind]

    return RecapOut(
        summary=meeting.summary,
        summary_edited_at=meeting.summary_edited_at,
        follow_ups=[_follow_up_out(f) for f in follow_ups],
        key_points=[
            KeyPointOut(id=str(i.id), title=i.title, text=i.text, at_ms=i.at_ms)
            for i in of_kind("key_point")
        ],
        chapters=[
            ChapterOut(id=str(i.id), title=i.title, at_ms=i.at_ms) for i in of_kind("chapter")
        ],
        highlights=[
            TextItemOut(id=str(i.id), text=i.text, at_ms=i.at_ms) for i in of_kind("highlight")
        ],
        questions=[
            TextItemOut(id=str(i.id), text=i.text, at_ms=i.at_ms) for i in of_kind("question")
        ],
    )


async def get_transcript(
    session: AsyncSession, meeting_id: uuid.UUID, q: str | None
) -> TranscriptOut:
    stmt = (
        select(TranscriptSegment, _speaker_name())
        .join(
            MeetingParticipant,
            MeetingParticipant.id == TranscriptSegment.participant_id,
            isouter=True,
        )
        .where(TranscriptSegment.meeting_id == meeting_id)
        .order_by(TranscriptSegment.seq)
    )
    needle = (q or "").strip()
    if needle:
        stmt = stmt.where(
            or_(
                TranscriptSegment.text.icontains(needle, autoescape=True),
                _speaker_name().icontains(needle, autoescape=True),
            )
        )
    rows = (await session.execute(stmt)).all()
    return TranscriptOut(
        segments=[
            SegmentOut(
                id=str(seg.id),
                seq=seg.seq,
                start_ms=seg.start_ms,
                end_ms=seg.end_ms,
                participant_id=_opt(seg.participant_id),
                speaker=speaker,
                text=seg.text,
            )
            for seg, speaker in rows
        ]
    )


async def get_people(session: AsyncSession, meeting_id: uuid.UUID) -> PeopleOut:
    talk = func.coalesce(func.sum(TranscriptSegment.end_ms - TranscriptSegment.start_ms), 0)
    rows = (
        await session.execute(
            select(MeetingParticipant, talk.label("talk_ms"))
            .join(
                TranscriptSegment,
                TranscriptSegment.participant_id == MeetingParticipant.id,
                isouter=True,
            )
            .where(MeetingParticipant.meeting_id == meeting_id)
            .group_by(MeetingParticipant.id)
            .order_by(talk.desc(), MeetingParticipant.created_at, MeetingParticipant.id)
        )
    ).all()
    total = sum(int(ms) for _, ms in rows)
    return PeopleOut(
        people=[
            PersonOut(
                participant_id=str(p.id),
                display_name=p.display_name,
                speaker_label=p.speaker_label,
                talk_ms=int(ms),
                share=int(ms) / total if total else 0.0,
            )
            for p, ms in rows
        ]
    )


async def rename_participant(
    session: AsyncSession, meeting_id: uuid.UUID, participant_id: uuid.UUID, display_name: str
) -> ParticipantOut:
    row = await session.scalar(
        select(MeetingParticipant).where(
            MeetingParticipant.id == participant_id, MeetingParticipant.meeting_id == meeting_id
        )
    )
    if row is None:
        raise AppError("participant_not_found", "Participant not found.", status_code=404)
    row.display_name = display_name
    await session.flush()
    return ParticipantOut(
        participant_id=str(row.id), display_name=row.display_name, speaker_label=row.speaker_label
    )


def _follow_up_query() -> Select[FollowUp, str]:
    """Follow-ups of ready, non-deleted meetings, with the meeting title."""
    return (
        select(FollowUp, Meeting.title)
        .join(Meeting, Meeting.id == FollowUp.meeting_id)
        .where(Meeting.status == "ready", Meeting.deleted_at.is_(None))
    )


def _item(row: FollowUp, title: str) -> FollowUpItemOut:
    return FollowUpItemOut(
        **_follow_up_out(row).model_dump(), meeting_id=str(row.meeting_id), meeting_title=title
    )


async def list_follow_ups(
    session: AsyncSession, user_id: uuid.UUID, owner: Literal["me", "all"], state: str | None
) -> FollowUpsOut:
    stmt = _follow_up_query()
    if owner == "me":
        stmt = stmt.where(FollowUp.owner_user_id == user_id)
    if state:
        stmt = stmt.where(FollowUp.state == state)
    stmt = stmt.order_by(
        (FollowUp.state == "done").asc(),
        func.coalesce(Meeting.started_at, Meeting.created_at).desc(),
        Meeting.id,
        FollowUp.at_ms.asc().nulls_last(),
        FollowUp.created_at,
        FollowUp.id,
    ).limit(MAX_FOLLOW_UPS)
    return FollowUpsOut(items=[_item(f, t) for f, t in (await session.execute(stmt)).all()])


async def set_follow_up_state(
    session: AsyncSession, follow_up_id: uuid.UUID, state: str
) -> FollowUpItemOut:
    found = (await session.execute(_follow_up_query().where(FollowUp.id == follow_up_id))).first()
    if found is None:
        raise AppError("follow_up_not_found", "Follow-up not found.", status_code=404)
    row, title = found
    if row.state != state:
        row.state = state
        row.done_at = datetime.now(UTC) if state == "done" else None
        await session.flush()
    return _item(row, title)


async def count_open_mine(session: AsyncSession, user_id: uuid.UUID) -> FollowUpCountOut:
    total = await session.scalar(
        select(func.count())
        .select_from(FollowUp)
        .join(Meeting, Meeting.id == FollowUp.meeting_id)
        .where(
            and_(
                Meeting.status == "ready",
                Meeting.deleted_at.is_(None),
                FollowUp.owner_user_id == user_id,
                FollowUp.state == "open",
            )
        )
    )
    return FollowUpCountOut(open_mine=int(total or 0))


# ---- exports ----


async def export_transcript(session: AsyncSession, meeting_id: uuid.UUID) -> str:
    segments = (await get_transcript(session, meeting_id, None)).segments
    lines = [
        f"[{format_mmss(s.start_ms)}] {s.speaker or UNKNOWN_SPEAKER}: {s.text}" for s in segments
    ]
    return "\n".join(lines) + "\n" if lines else ""


async def export_recap(session: AsyncSession, meeting: Meeting) -> str:
    recap = await get_recap(session, meeting)
    when = meeting.started_at or meeting.created_at
    out = [f"# {meeting.title}", "", f"Date: {when.astimezone(UTC).date().isoformat()}", ""]
    if recap.summary:
        out += ["## Summary", "", recap.summary, ""]
    if recap.follow_ups:
        out += ["## Follow-ups", ""]
        for f in recap.follow_ups:
            box = "x" if f.state == "done" else " "
            owner = f" (owner: {f.owner_name})" if f.owner_name else ""
            stamp = f" [{format_mmss(f.at_ms)}]" if f.at_ms is not None else ""
            out.append(f"- [{box}] {f.text}{owner}{stamp}")
        out.append("")
    if recap.key_points:
        out += ["## Key points", ""]
        for k in recap.key_points:
            stamp = f" [{format_mmss(k.at_ms)}]" if k.at_ms is not None else ""
            detail = f": {k.text}" if k.text else ""
            out.append(f"- **{k.title}**{stamp}{detail}")
        out.append("")
    if recap.chapters:
        out += ["## Chapters", ""]
        for c in recap.chapters:
            stamp = f"[{format_mmss(c.at_ms)}] " if c.at_ms is not None else ""
            out.append(f"- {stamp}{c.title}")
        out.append("")
    return "\n".join(out)
