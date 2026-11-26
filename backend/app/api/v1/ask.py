import json
import logging
import uuid
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, field_validator

from app.api.deps import CsrfSession, Current, Db
from app.core.settings import get_settings
from app.db.session import tenant_session
from app.providers.base import ProviderError
from app.providers.metering import MeteredLlm
from app.providers.registry import get_llm
from app.services import ask
from app.services import conversations as svc

router = APIRouter(prefix="/conversations", tags=["ask"])
logger = logging.getLogger(__name__)

MAX_QUESTION_LENGTH = 2000
UNAVAILABLE = {
    "code": "provider_unavailable",
    "message": "The assistant is unavailable right now. Try again.",
}


class ConversationIn(BaseModel):
    scope_meeting_id: uuid.UUID | None = None


class MessageIn(BaseModel):
    text: str

    @field_validator("text")
    @classmethod
    def _text(cls, value: str) -> str:
        value = value.strip()
        if not 1 <= len(value) <= MAX_QUESTION_LENGTH:
            raise ValueError(f"text must be 1 to {MAX_QUESTION_LENGTH} characters")
        return value


def _sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@router.get("")
async def list_conversations(current: Current) -> svc.ConversationListOut:
    async with tenant_session(current.schema_name) as session:
        return await svc.list_conversations(session, current.user.id)


@router.post("", status_code=201)
async def create_conversation(body: ConversationIn, current: CsrfSession) -> svc.ConversationOut:
    async with tenant_session(current.schema_name) as session:
        return await svc.create_conversation(session, current.user.id, body.scope_meeting_id)


@router.get("/{conversation_id}")
async def get_conversation(
    conversation_id: uuid.UUID, current: Current
) -> svc.ConversationDetailOut:
    async with tenant_session(current.schema_name) as session:
        return await svc.get_detail(session, current.user.id, conversation_id)


@router.delete("/{conversation_id}", status_code=204)
async def delete_conversation(conversation_id: uuid.UUID, current: CsrfSession) -> Response:
    async with tenant_session(current.schema_name) as session:
        await svc.delete_conversation(session, current.user.id, conversation_id)
    return Response(status_code=204)


async def _answer(
    schema: str, conversation_id: uuid.UUID, scope: uuid.UUID | None, question: str
) -> AsyncIterator[str]:
    """Stream the answer. The answer is stored (and committed) before the last events."""
    chunks: list[ask.RetrievedChunk] = []
    failed = False
    raw = ""
    async with tenant_session(schema) as session:
        try:
            chunks = await ask.search(session, question, scope)
            if not chunks:
                raw = ask.not_found_text(scope is not None)
                yield _sse("token", {"text": raw})
            else:
                llm = MeteredLlm(get_llm(), session, None)
                pieces = llm.stream(
                    ask.build_messages(question, chunks), max_tokens=get_settings().ask_max_tokens
                )
                async for piece in pieces:
                    raw += piece
                    yield _sse("token", {"text": piece})
        except ProviderError:
            logger.exception("ask failed for conversation %s", conversation_id)
            failed = True
        message_id, citations = await svc.save_answer(
            session, conversation_id, raw, "failed" if failed else "done", chunks
        )
    if failed:
        yield _sse("error", UNAVAILABLE)
        return
    items = [c.model_dump() for c in citations]
    yield _sse("citations", {"items": items})
    yield _sse("done", {"message_id": str(message_id)})


@router.post("/{conversation_id}/messages")
async def post_message(
    conversation_id: uuid.UUID, body: MessageIn, current: CsrfSession, db: Db
) -> StreamingResponse:
    await db.close()  # do not hold a public-schema connection while streaming
    async with tenant_session(current.schema_name) as session:
        conversation = await svc.get_conversation(session, current.user.id, conversation_id)
        scope = conversation.scope_meeting_id
        await svc.add_user_message(session, conversation, body.text)
    return StreamingResponse(
        _answer(current.schema_name, conversation_id, scope, body.text),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
