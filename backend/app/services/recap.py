"""Recap pipeline logic: prompt, JSON parsing and validation, owner matching, DB writes."""

import json
import uuid
from bisect import bisect_right
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic import BaseModel, ValidationError
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.org import FollowUp, Meeting, RecapItem
from app.providers.types import RECAP_MARKER, ChatMessage

NO_SPEECH_SUMMARY = "No speech was detected in this recording."
UNKNOWN_SPEAKER = "Unknown"
TITLE_WORDS = 6
LANGUAGE_NAMES = {"en": "English", "vi": "Vietnamese"}

SYSTEM_PROMPT = (
    "You write meeting recaps. Use only what is said in the transcript. "
    "Reply with one JSON object and nothing else."
)
INSTRUCTIONS = """\
{marker}
Write a recap of the meeting transcript below. Write all text in {language}.
Each transcript line looks like "[at_ms=<start_ms>] <speaker>: <text>".
Return one JSON object with exactly these keys:
{{
  "summary": "2 to 4 sentences",
  "follow_ups": [{{"text": "action item", "owner": "speaker name or null", "at_ms": 0}}],
  "key_points": [{{"title": "short title", "text": "one sentence", "at_ms": 0}}],
  "chapters": [{{"title": "topic title", "at_ms": 0}}],
  "highlights": [{{"text": "notable moment", "at_ms": 0}}],
  "questions": [{{"text": "question that was asked", "at_ms": 0}}]
}}
Rules: every at_ms must be an at_ms value that appears in the transcript. Use an empty list
when a section has nothing to report. Do not invent facts, names or dates.

Transcript:
{transcript}
"""


@dataclass(frozen=True)
class PromptLine:
    start_ms: int
    speaker: str
    text: str


def build_messages(lines: list[PromptLine], language: str) -> list[ChatMessage]:
    transcript = "\n".join(f"[at_ms={ln.start_ms}] {ln.speaker}: {ln.text}" for ln in lines)
    user = INSTRUCTIONS.format(
        marker=RECAP_MARKER,
        language=LANGUAGE_NAMES.get(language, "English"),
        transcript=transcript,
    )
    return [ChatMessage("system", SYSTEM_PROMPT), ChatMessage("user", user)]


# ---- parsing and validation ----


class RecapParseError(Exception):
    """The model reply is not a usable recap JSON object."""


class _FollowUpIn(BaseModel):
    text: str
    owner: str | None = None
    at_ms: int | None = None


class _KeyPointIn(BaseModel):
    title: str | None = None
    text: str
    at_ms: int | None = None


class _ChapterIn(BaseModel):
    title: str
    at_ms: int | None = None


class _TextIn(BaseModel):
    text: str
    at_ms: int | None = None


@dataclass
class Recap:
    summary: str = ""
    follow_ups: list[_FollowUpIn] = field(default_factory=list)
    key_points: list[_KeyPointIn] = field(default_factory=list)
    chapters: list[_ChapterIn] = field(default_factory=list)
    highlights: list[_TextIn] = field(default_factory=list)
    questions: list[_TextIn] = field(default_factory=list)


def _items[M: BaseModel](raw: Any, model: type[M]) -> list[M]:
    """Valid items of a list; a missing list is empty and bad items are skipped."""
    if not isinstance(raw, list):
        return []
    found: list[M] = []
    for entry in raw:
        try:
            item = model.model_validate(entry)
        except ValidationError:
            continue
        main = getattr(item, "text", None) or getattr(item, "title", None)
        if not main or not main.strip():
            continue
        found.append(item)
    return found


def _strip_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else ""
        text = text.rsplit("```", 1)[0]
    return text.strip()


def parse_recap(raw: str) -> Recap:
    try:
        data = json.loads(_strip_fence(raw))
    except ValueError as exc:
        raise RecapParseError("the reply is not valid JSON") from exc
    if not isinstance(data, dict):
        raise RecapParseError("the reply is not a JSON object")
    summary = data.get("summary", "")
    if summary is None:
        summary = ""
    if not isinstance(summary, str):
        raise RecapParseError("summary is not a string")
    return Recap(
        summary=summary.strip(),
        follow_ups=_items(data.get("follow_ups"), _FollowUpIn),
        key_points=_items(data.get("key_points"), _KeyPointIn),
        chapters=_items(data.get("chapters"), _ChapterIn),
        highlights=_items(data.get("highlights"), _TextIn),
        questions=_items(data.get("questions"), _TextIn),
    )


def snap_at_ms(at_ms: int, starts: list[int]) -> int:
    """Start of the latest segment at or before at_ms (the first start if none is)."""
    index = bisect_right(starts, at_ms)
    return starts[max(index - 1, 0)]


def _valid_at[T: BaseModel](items: list[T], starts: list[int], duration_ms: int | None) -> list[T]:
    """Drop items outside the recording and snap the others to a segment start."""
    kept: list[T] = []
    for item in items:
        at_ms: int | None = getattr(item, "at_ms", None)
        if at_ms is not None:
            if at_ms < 0 or (duration_ms is not None and at_ms > duration_ms):
                continue
            if starts:
                item = item.model_copy(update={"at_ms": snap_at_ms(at_ms, starts)})
        kept.append(item)
    return kept


def validate_recap(recap: Recap, starts: list[int], duration_ms: int | None) -> Recap:
    """Return a copy with timestamps validated and snapped; starts must be sorted."""
    return Recap(
        summary=recap.summary,
        follow_ups=_valid_at(recap.follow_ups, starts, duration_ms),
        key_points=_valid_at(recap.key_points, starts, duration_ms),
        chapters=_valid_at(recap.chapters, starts, duration_ms),
        highlights=_valid_at(recap.highlights, starts, duration_ms),
        questions=_valid_at(recap.questions, starts, duration_ms),
    )


def key_point_title(title: str | None, text: str) -> str:
    if title and title.strip():
        return title.strip()
    return " ".join(text.split()[:TITLE_WORDS])


@dataclass(frozen=True)
class Member:
    user_id: uuid.UUID
    name: str
    email: str


def match_owner(owner: str | None, members: list[Member]) -> uuid.UUID | None:
    """Member whose name or email local part equals owner (case-insensitive), if unique."""
    wanted = (owner or "").strip().casefold()
    if not wanted:
        return None
    found = {
        m.user_id
        for m in members
        if wanted in (m.name.strip().casefold(), m.email.split("@", 1)[0].strip().casefold())
    }
    return next(iter(found)) if len(found) == 1 else None


# ---- database writes ----


def _by_time[T: BaseModel](items: list[T]) -> list[T]:
    """Chronological order; items without a time go last. The sort is stable."""
    return sorted(items, key=lambda i: (getattr(i, "at_ms", None) is None, getattr(i, "at_ms", 0)))


async def clear_recap(session: AsyncSession, meeting_id: uuid.UUID) -> None:
    """Remove recap items and the follow-ups still open; done follow-ups are kept."""
    await session.execute(delete(RecapItem).where(RecapItem.meeting_id == meeting_id))
    await session.execute(
        delete(FollowUp).where(
            FollowUp.meeting_id == meeting_id,
            FollowUp.origin == "recap",
            FollowUp.state == "open",
        )
    )


async def replace_recap(
    session: AsyncSession, meeting: Meeting, recap: Recap, members: list[Member]
) -> None:
    """Write the recap in the caller's transaction and move the meeting to the "filing" stage.

    The summary is only set when the user has not edited it. Follow-ups the user already
    marked done are kept; a new follow-up with the same text as a kept one is not added.
    """
    await clear_recap(session, meeting.id)
    if meeting.summary_edited_at is None:
        meeting.summary = recap.summary or None
    kinds: list[tuple[str, list[RecapItem]]] = [
        (
            "key_point",
            [
                RecapItem(title=key_point_title(i.title, i.text), text=i.text, at_ms=i.at_ms)
                for i in _by_time(recap.key_points)
            ],
        ),
        ("chapter", [RecapItem(title=i.title, at_ms=i.at_ms) for i in _by_time(recap.chapters)]),
        ("highlight", [RecapItem(text=i.text, at_ms=i.at_ms) for i in _by_time(recap.highlights)]),
        ("question", [RecapItem(text=i.text, at_ms=i.at_ms) for i in _by_time(recap.questions)]),
    ]
    for kind, rows in kinds:
        for seq, row in enumerate(rows):
            row.meeting_id, row.kind, row.seq = meeting.id, kind, seq
            session.add(row)
    kept = {
        t.casefold()
        for t in await session.scalars(
            select(FollowUp.text).where(
                FollowUp.meeting_id == meeting.id, FollowUp.origin == "recap"
            )
        )
    }
    base = datetime.now(UTC)
    for seq, item in enumerate(_by_time(recap.follow_ups)):
        if item.text.strip().casefold() in kept:
            continue
        owner = (item.owner or "").strip() or None
        session.add(
            FollowUp(
                meeting_id=meeting.id,
                text=item.text.strip(),
                owner_name=owner,
                owner_user_id=match_owner(owner, members),
                at_ms=item.at_ms,
                state="open",
                origin="recap",
                created_at=base + timedelta(microseconds=seq),  # keeps the recap order
            )
        )
    meeting.stage, meeting.status, meeting.error = "filing", "processing", None
    await session.flush()
