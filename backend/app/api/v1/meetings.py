import asyncio
import json
import logging
import mimetypes
import time
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import PurePosixPath
from typing import Annotated, Any, Literal

from fastapi import APIRouter, File, Form, Query, Request, Response, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, field_validator
from sqlalchemy import delete, select

from app.api.deps import CsrfSession, Current, Db
from app.core.errors import AppError
from app.core.settings import get_settings
from app.db.models.org import Meeting, Recording
from app.db.session import tenant_session
from app.jobs import queue
from app.services import meetings as svc
from app.services.ranges import RangeNotSatisfiableError, parse_range
from app.storage import get_storage, iter_file, meeting_key

router = APIRouter(prefix="/meetings", tags=["meetings"])
logger = logging.getLogger(__name__)

READ_CHUNK = 1024 * 1024
MAX_TITLE_LENGTH = 200


async def _limited(upload: UploadFile, max_bytes: int) -> AsyncIterator[bytes]:
    total = 0
    while chunk := await upload.read(READ_CHUNK):
        total += len(chunk)
        if total > max_bytes:
            raise AppError(
                "file_too_large",
                "The file is too large.",
                status_code=413,
                details={"max_upload_bytes": max_bytes},
            )
        yield chunk


@router.post("/uploads", status_code=201)
async def upload_meeting(
    current: CsrfSession,
    file: Annotated[UploadFile, File()],
    language: Annotated[Literal["en", "vi"], Form()] = "en",
    title: Annotated[str | None, Form()] = None,
) -> svc.MeetingOut:
    settings = get_settings()
    filename = PurePosixPath((file.filename or "").replace("\\", "/")).name
    stem, ext = PurePosixPath(filename).stem, PurePosixPath(filename).suffix.lstrip(".").lower()
    if ext not in settings.upload_extensions:
        raise AppError(
            "unsupported_file_type",
            "This file type is not supported.",
            details={"allowed": sorted(settings.upload_extensions)},
        )
    meeting_id = uuid.uuid4()
    key = meeting_key(current.schema_name, meeting_id, f"original.{ext}")
    storage = get_storage()
    size = await storage.save(_limited(file, int(settings.max_upload_mb * 1024 * 1024)), key)
    mime = file.content_type or mimetypes.guess_type(filename)[0] or "application/octet-stream"
    try:
        async with tenant_session(current.schema_name) as session:
            meeting = Meeting(
                id=meeting_id,
                title=(title or "").strip()[:MAX_TITLE_LENGTH] or stem or "Untitled meeting",
                source="upload",
                platform="file",
                language=language,
                status="processing",
                stage="uploading",
                started_at=datetime.now(UTC),
                owner_id=current.user.id,
            )
            session.add(meeting)
            await session.flush()
            session.add(
                Recording(meeting_id=meeting_id, original_path=key, mime_type=mime, size_bytes=size)
            )
            await session.flush()
            await queue.enqueue(session, "decode", meeting_id)
            return svc.to_summary(meeting, [])
    except BaseException:
        await storage.delete(key)
        raise


@router.get("")
async def list_meetings(
    current: Current,
    status: Literal["processing", "ready", "incomplete"] | None = None,
    q: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    cursor: str | None = None,
) -> dict[str, Any]:
    async with tenant_session(current.schema_name) as session:
        page = await svc.list_meetings(session, status, q, limit, cursor)
    return {
        "items": [item.model_dump(mode="json") for item in page["items"]],
        "next_cursor": page["next_cursor"],
        "meta": page["meta"],
    }


@router.get("/{meeting_id}")
async def get_meeting(meeting_id: uuid.UUID, current: Current) -> svc.MeetingDetailOut:
    async with tenant_session(current.schema_name) as session:
        meeting = await svc.get_meeting(session, meeting_id)
        people = await svc.participants_for(session, [meeting_id])
        return svc.to_detail(meeting, people[meeting_id])


class MeetingPatch(BaseModel):
    title: str | None = None
    summary: str | None = None

    @field_validator("title")
    @classmethod
    def _title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value or len(value) > MAX_TITLE_LENGTH:
            raise ValueError(f"title must be 1 to {MAX_TITLE_LENGTH} characters")
        return value


@router.patch("/{meeting_id}")
async def patch_meeting(
    meeting_id: uuid.UUID, body: MeetingPatch, current: CsrfSession
) -> svc.MeetingDetailOut:
    if not body.model_fields_set:
        raise AppError("validation_error", "Nothing to update", status_code=400)
    async with tenant_session(current.schema_name) as session:
        meeting = await svc.get_meeting(session, meeting_id)
        if body.title is not None:
            meeting.title = body.title
        if "summary" in body.model_fields_set:
            meeting.summary = body.summary
            meeting.summary_edited_at = datetime.now(UTC)
        await session.flush()
        people = await svc.participants_for(session, [meeting_id])
        return svc.to_detail(meeting, people[meeting_id])


@router.delete("/{meeting_id}", status_code=204)
async def delete_meeting(meeting_id: uuid.UUID, current: CsrfSession) -> Response:
    async with tenant_session(current.schema_name) as session:
        await svc.get_meeting(session, meeting_id)
        recording = await session.scalar(
            select(Recording).where(Recording.meeting_id == meeting_id)
        )
        keys = []
        if recording is not None:
            keys = [k for k in (recording.original_path, recording.audio_path) if k]
        await session.execute(delete(Meeting).where(Meeting.id == meeting_id))
    storage = get_storage()
    for key in keys:
        try:
            await storage.delete(key)
        except OSError:
            logger.warning("could not delete stored file %s", key)
    return Response(status_code=204)


@router.post("/{meeting_id}/retry")
async def retry_meeting(meeting_id: uuid.UUID, current: CsrfSession) -> svc.MeetingDetailOut:
    async with tenant_session(current.schema_name) as session:
        meeting = await svc.get_meeting(session, meeting_id)
        if await svc.has_active_job(session, meeting_id):
            raise AppError(
                "stage_already_running", "This stage is already running.", status_code=409
            )
        if meeting.status != "incomplete":
            raise AppError("not_retryable", "Only incomplete meetings can be retried.", 409)
        stage = meeting.stage or "uploading"
        meeting.stage = stage
        meeting.status = "processing"
        meeting.error = None
        await session.flush()
        await queue.enqueue(session, svc.STAGE_JOB[stage], meeting_id)
        people = await svc.participants_for(session, [meeting_id])
        return svc.to_detail(meeting, people[meeting_id])


def _sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


async def _meeting_events(schema: str, meeting_id: uuid.UUID) -> AsyncIterator[str]:
    settings = get_settings()
    deadline = time.monotonic() + settings.sse_max_seconds
    last: tuple[str | None, str] | None = None
    while True:
        async with tenant_session(schema) as session:
            meeting = await session.scalar(
                select(Meeting).where(Meeting.id == meeting_id, Meeting.deleted_at.is_(None))
            )
            current = None if meeting is None else (meeting.stage, meeting.status)
            error = None if meeting is None else meeting.error
        if current is None:
            return
        if current != last:
            if last is None or last[0] != current[0]:
                yield _sse("stage", {"stage": current[0]})
            if last is None or last[1] != current[1]:
                yield _sse("status", {"status": current[1], "error": error})
            last = current
        if current[1] in ("ready", "incomplete") or time.monotonic() >= deadline:
            return
        await asyncio.sleep(settings.sse_poll_interval_seconds)


@router.get("/{meeting_id}/events")
async def meeting_events(meeting_id: uuid.UUID, current: Current, db: Db) -> StreamingResponse:
    await db.close()  # do not hold a public-schema connection while streaming
    async with tenant_session(current.schema_name) as session:
        await svc.get_meeting(session, meeting_id)
    return StreamingResponse(
        _meeting_events(current.schema_name, meeting_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/{meeting_id}/audio")
async def meeting_audio(meeting_id: uuid.UUID, request: Request, current: Current) -> Response:
    async with tenant_session(current.schema_name) as session:
        await svc.get_meeting(session, meeting_id)
        audio_key = await session.scalar(
            select(Recording.audio_path).where(Recording.meeting_id == meeting_id)
        )
    storage = get_storage()
    if not audio_key or not await storage.exists(audio_key):
        raise AppError("audio_not_found", "Audio is not ready yet.", status_code=404)
    path = storage.open(audio_key)
    size = path.stat().st_size
    base = {"Accept-Ranges": "bytes", "Content-Type": "audio/wav"}
    try:
        wanted = parse_range(request.headers.get("range"), size)
    except RangeNotSatisfiableError:
        return Response(status_code=416, headers={**base, "Content-Range": f"bytes */{size}"})
    if wanted is None:
        return StreamingResponse(
            iter_file(path), headers={**base, "Content-Length": str(size)}, media_type="audio/wav"
        )
    headers = {
        **base,
        "Content-Length": str(wanted.length),
        "Content-Range": f"bytes {wanted.start}-{wanted.end}/{size}",
    }
    return StreamingResponse(
        iter_file(path, wanted.start, wanted.end),
        status_code=206,
        headers=headers,
        media_type="audio/wav",
    )
