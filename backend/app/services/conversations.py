"""Ask conversations: chat list, messages and citations. Conversations belong to one user."""

import uuid
from datetime import datetime

from pydantic import BaseModel
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.db.models.org import Citation, Conversation, Meeting, Message
from app.services import meetings as meetings_svc
from app.services.ask import RetrievedChunk, cited_indexes, strip_labels

TITLE_LENGTH = 60


class ConversationOut(BaseModel):
    id: str
    title: str | None
    scope_meeting_id: str | None
    updated_at: datetime


class ConversationListOut(BaseModel):
    items: list[ConversationOut]


class CitationOut(BaseModel):
    meeting_id: str
    meeting_title: str
    at_ms: int | None


class MessageOut(BaseModel):
    id: str
    role: str
    text: str
    status: str
    created_at: datetime
    citations: list[CitationOut]


class ConversationDetailOut(BaseModel):
    id: str
    title: str | None
    scope_meeting_id: str | None
    messages: list[MessageOut]


def conversation_not_found() -> AppError:
    return AppError("conversation_not_found", "Conversation not found.", status_code=404)


def _out(row: Conversation) -> ConversationOut:
    return ConversationOut(
        id=str(row.id),
        title=row.title,
        scope_meeting_id=None if row.scope_meeting_id is None else str(row.scope_meeting_id),
        updated_at=row.updated_at,
    )


async def get_conversation(
    session: AsyncSession, user_id: uuid.UUID, conversation_id: uuid.UUID
) -> Conversation:
    row = await session.scalar(
        select(Conversation).where(
            Conversation.id == conversation_id, Conversation.user_id == user_id
        )
    )
    if row is None:
        raise conversation_not_found()
    return row


async def list_conversations(session: AsyncSession, user_id: uuid.UUID) -> ConversationListOut:
    rows = await session.scalars(
        select(Conversation)
        .where(Conversation.user_id == user_id)
        .order_by(Conversation.updated_at.desc(), Conversation.id)
    )
    return ConversationListOut(items=[_out(r) for r in rows])


async def create_conversation(
    session: AsyncSession, user_id: uuid.UUID, scope_meeting_id: uuid.UUID | None
) -> ConversationOut:
    if scope_meeting_id is not None:
        await meetings_svc.get_meeting(session, scope_meeting_id)  # 404 meeting_not_found
    row = Conversation(user_id=user_id, scope_meeting_id=scope_meeting_id)
    session.add(row)
    await session.flush()
    await session.refresh(row)
    return _out(row)


async def delete_conversation(
    session: AsyncSession, user_id: uuid.UUID, conversation_id: uuid.UUID
) -> None:
    row = await get_conversation(session, user_id, conversation_id)
    await session.execute(delete(Conversation).where(Conversation.id == row.id))


async def get_detail(
    session: AsyncSession, user_id: uuid.UUID, conversation_id: uuid.UUID
) -> ConversationDetailOut:
    row = await get_conversation(session, user_id, conversation_id)
    messages = list(
        await session.scalars(
            select(Message)
            .where(Message.conversation_id == row.id)
            .order_by(Message.created_at, Message.role.desc(), Message.id)  # user before assistant
        )
    )
    cited: dict[uuid.UUID, list[CitationOut]] = {m.id: [] for m in messages}
    if messages:
        rows = await session.execute(
            select(Citation.message_id, Citation.meeting_id, Meeting.title, Citation.at_ms)
            .join(Meeting, Meeting.id == Citation.meeting_id)
            .where(Citation.message_id.in_(cited))
            .order_by(Citation.seq)
        )
        for message_id, meeting_id, title, at_ms in rows:
            cited[message_id].append(
                CitationOut(meeting_id=str(meeting_id), meeting_title=title, at_ms=at_ms)
            )
    return ConversationDetailOut(
        id=str(row.id),
        title=row.title,
        scope_meeting_id=None if row.scope_meeting_id is None else str(row.scope_meeting_id),
        messages=[
            MessageOut(
                id=str(m.id),
                role=m.role,
                text=m.text,
                status=m.status,
                created_at=m.created_at,
                citations=cited[m.id],
            )
            for m in messages
        ],
    )


async def add_user_message(session: AsyncSession, conversation: Conversation, text: str) -> None:
    """Save the question; the first question also becomes the title."""
    session.add(Message(conversation_id=conversation.id, role="user", text=text, status="done"))
    if not conversation.title:
        conversation.title = " ".join(text.split())[:TITLE_LENGTH]
    await touch(session, conversation.id)


async def touch(session: AsyncSession, conversation_id: uuid.UUID) -> None:
    await session.execute(
        update(Conversation).where(Conversation.id == conversation_id).values(updated_at=func.now())
    )


async def save_answer(
    session: AsyncSession,
    conversation_id: uuid.UUID,
    raw_text: str,
    status: str,
    chunks: list[RetrievedChunk],
) -> tuple[uuid.UUID, list[CitationOut]]:
    """Store the assistant message and, when it is done, citations for the labels it used.

    The stored text has the [cN] labels removed. Returns the message id and the citations.
    """
    message = Message(
        conversation_id=conversation_id,
        role="assistant",
        text=strip_labels(raw_text),
        status=status,
    )
    session.add(message)
    await session.flush()
    out: list[CitationOut] = []
    indexes = cited_indexes(raw_text, len(chunks)) if status == "done" else []
    for seq, index in enumerate(indexes):
        chunk = chunks[index]
        session.add(
            Citation(
                message_id=message.id,
                meeting_id=chunk.meeting_id,
                chunk_id=chunk.chunk_id,
                at_ms=chunk.start_ms,
                seq=seq,
            )
        )
        out.append(
            CitationOut(
                meeting_id=str(chunk.meeting_id),
                meeting_title=chunk.meeting_title,
                at_ms=chunk.start_ms,
            )
        )
    await session.flush()
    await touch(session, conversation_id)
    return message.id, out
