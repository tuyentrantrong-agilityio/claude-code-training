import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Computed,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import TIMESTAMP, TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import UserDefinedType

from app.db.base import OrgBase


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )


def _meeting_fk(nullable: bool = False) -> Mapped[uuid.UUID]:
    return mapped_column(ForeignKey("meetings.id", ondelete="CASCADE"), nullable=nullable)


def _ts() -> Mapped[datetime | None]:
    return mapped_column(TIMESTAMP(timezone=True))


def _created() -> Mapped[datetime]:
    return mapped_column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)


def _updated() -> Mapped[datetime]:
    return mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class Meeting(OrgBase):
    __tablename__ = "meetings"
    __table_args__ = (
        CheckConstraint("source IN ('upload', 'bot', 'desktop')", name="source"),
        CheckConstraint(
            "platform IN ('file', 'meet', 'zoom', 'teams', 'desktop')", name="platform"
        ),
        CheckConstraint("language IN ('en', 'vi')", name="language"),
        CheckConstraint("status IN ('processing', 'ready', 'incomplete')", name="status"),
        CheckConstraint(
            "stage IS NULL OR stage IN ('uploading', 'transcribing', 'summarizing', 'filing')",
            name="stage",
        ),
        Index("ix_meetings_status_started_at", "status", text("started_at DESC")),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    title: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    platform: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    stage: Mapped[str | None] = mapped_column(Text)
    error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = _ts()
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    owner_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    summary: Mapped[str | None] = mapped_column(Text)
    summary_edited_at: Mapped[datetime | None] = _ts()
    deleted_at: Mapped[datetime | None] = _ts()
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = _updated()


class Recording(OrgBase):
    __tablename__ = "recordings"
    __table_args__ = (UniqueConstraint("meeting_id"),)

    id: Mapped[uuid.UUID] = _uuid_pk()
    meeting_id: Mapped[uuid.UUID] = _meeting_fk()
    original_path: Mapped[str | None] = mapped_column(Text)
    audio_path: Mapped[str | None] = mapped_column(Text)
    mime_type: Mapped[str | None] = mapped_column(Text)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    expires_at: Mapped[datetime | None] = _ts()
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = _updated()


class MeetingParticipant(OrgBase):
    __tablename__ = "meeting_participants"

    id: Mapped[uuid.UUID] = _uuid_pk()
    meeting_id: Mapped[uuid.UUID] = _meeting_fk()
    speaker_label: Mapped[str | None] = mapped_column(Text)
    display_name: Mapped[str | None] = mapped_column(Text)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = _updated()


class TranscriptSegment(OrgBase):
    __tablename__ = "transcript_segments"
    __table_args__ = (
        UniqueConstraint("meeting_id", "seq"),
        CheckConstraint("start_ms <= end_ms AND start_ms >= 0", name="time_range"),
        Index("ix_transcript_segments_meeting_id_start_ms", "meeting_id", "start_ms"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    meeting_id: Mapped[uuid.UUID] = _meeting_fk()
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    start_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    end_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    participant_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("meeting_participants.id"))
    text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = _updated()


class RecapItem(OrgBase):
    __tablename__ = "recap_items"
    __table_args__ = (
        UniqueConstraint("meeting_id", "kind", "seq"),
        CheckConstraint("kind IN ('key_point', 'chapter', 'highlight', 'question')", name="kind"),
        CheckConstraint("at_ms IS NULL OR at_ms >= 0", name="at_ms"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    meeting_id: Mapped[uuid.UUID] = _meeting_fk()
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    at_ms: Mapped[int | None] = mapped_column(Integer)
    title: Mapped[str | None] = mapped_column(Text)
    text: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = _updated()


class FollowUp(OrgBase):
    __tablename__ = "follow_ups"
    __table_args__ = (
        CheckConstraint("state IN ('open', 'done')", name="state"),
        CheckConstraint("origin IN ('recap', 'suggested')", name="origin"),
        Index("ix_follow_ups_owner_user_id_state", "owner_user_id", "state"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    meeting_id: Mapped[uuid.UUID] = _meeting_fk()
    text: Mapped[str] = mapped_column(Text, nullable=False)
    owner_name: Mapped[str | None] = mapped_column(Text)
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    at_ms: Mapped[int | None] = mapped_column(Integer)
    state: Mapped[str] = mapped_column(Text, server_default="open", nullable=False)
    origin: Mapped[str] = mapped_column(Text, server_default="recap", nullable=False)
    done_at: Mapped[datetime | None] = _ts()
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = _updated()


class Job(OrgBase):
    __tablename__ = "jobs"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('decode', 'transcribe', 'recap', 'index', 'cleanup')", name="kind"
        ),
        CheckConstraint("state IN ('queued', 'running', 'succeeded', 'failed')", name="state"),
        Index("ix_jobs_state_run_after", "state", "run_after"),
        Index(
            "uq_jobs_active_meeting_kind",
            "meeting_id",
            "kind",
            unique=True,
            postgresql_where=text("state IN ('queued', 'running')"),
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    meeting_id: Mapped[uuid.UUID | None] = _meeting_fk(nullable=True)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    state: Mapped[str] = mapped_column(Text, server_default="queued", nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, server_default="0", nullable=False)
    run_after: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    last_error: Mapped[str | None] = mapped_column(Text)
    locked_by: Mapped[str | None] = mapped_column(Text)
    locked_at: Mapped[datetime | None] = _ts()
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = _updated()


class UsageEvent(OrgBase):
    __tablename__ = "usage_events"

    id: Mapped[uuid.UUID] = _uuid_pk()
    meeting_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    function: Mapped[str | None] = mapped_column(Text)
    provider: Mapped[str | None] = mapped_column(Text)
    units: Mapped[Decimal | None] = mapped_column(Numeric)
    unit_kind: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = _updated()


class Vector(UserDefinedType[list[float]]):
    """pgvector column without a fixed dimension.

    Values are written and read with SQL (see app/services/ask.py); the ORM never loads it.
    """

    cache_ok = True

    def get_col_spec(self, **kw: object) -> str:
        return "vector"


class SearchChunk(OrgBase):
    __tablename__ = "search_chunks"
    __table_args__ = (
        UniqueConstraint("meeting_id", "seq"),
        Index("ix_search_chunks_tsv", "tsv", postgresql_using="gin"),
        Index("ix_search_chunks_meeting_id", "meeting_id"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    meeting_id: Mapped[uuid.UUID] = _meeting_fk()
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    start_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    end_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    tsv: Mapped[str | None] = mapped_column(
        TSVECTOR, Computed("to_tsvector('simple', text)", persisted=True), deferred=True
    )
    embedding: Mapped[list[float] | None] = mapped_column(Vector, deferred=True)
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = _updated()


class Conversation(OrgBase):
    __tablename__ = "conversations"
    __table_args__ = (
        Index("ix_conversations_user_id_updated_at", "user_id", text("updated_at DESC")),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    scope_meeting_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("meetings.id", ondelete="SET NULL")
    )
    title: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = _updated()


class Message(OrgBase):
    __tablename__ = "messages"
    __table_args__ = (
        CheckConstraint("role IN ('user', 'assistant')", name="role"),
        CheckConstraint("status IN ('streaming', 'done', 'failed')", name="status"),
        Index("ix_messages_conversation_id_created_at", "conversation_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(Text, nullable=False)
    text: Mapped[str] = mapped_column(Text, server_default="", nullable=False)
    status: Mapped[str] = mapped_column(Text, server_default="done", nullable=False)
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = _updated()


class Citation(OrgBase):
    __tablename__ = "citations"
    __table_args__ = (
        Index("ix_citations_message_id", "message_id"),
        Index("ix_citations_meeting_id", "meeting_id"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    message_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("messages.id", ondelete="CASCADE"), nullable=False
    )
    meeting_id: Mapped[uuid.UUID] = _meeting_fk()
    chunk_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("search_chunks.id", ondelete="SET NULL")
    )
    at_ms: Mapped[int | None] = mapped_column(Integer)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = _updated()
