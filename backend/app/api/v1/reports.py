import uuid

from fastapi import APIRouter, Response

from app.api.deps import CsrfSession, Current
from app.db.session import tenant_session
from app.services import meetings as svc
from app.services import reports

router = APIRouter(prefix="/meetings", tags=["reports"])


def _download(content: str, media_type: str, filename: str) -> Response:
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{meeting_id}/recap")
async def get_recap(meeting_id: uuid.UUID, current: Current) -> reports.RecapOut:
    async with tenant_session(current.schema_name) as session:
        meeting = await svc.get_meeting(session, meeting_id)
        return await reports.get_recap(session, meeting)


@router.get("/{meeting_id}/transcript")
async def get_transcript(
    meeting_id: uuid.UUID, current: Current, q: str | None = None
) -> reports.TranscriptOut:
    async with tenant_session(current.schema_name) as session:
        await svc.get_meeting(session, meeting_id)
        return await reports.get_transcript(session, meeting_id, q)


@router.get("/{meeting_id}/people")
async def get_people(meeting_id: uuid.UUID, current: Current) -> reports.PeopleOut:
    async with tenant_session(current.schema_name) as session:
        await svc.get_meeting(session, meeting_id)
        return await reports.get_people(session, meeting_id)


@router.patch("/{meeting_id}/participants/{participant_id}")
async def patch_participant(
    meeting_id: uuid.UUID,
    participant_id: uuid.UUID,
    body: reports.ParticipantPatch,
    current: CsrfSession,
) -> reports.ParticipantOut:
    async with tenant_session(current.schema_name) as session:
        await svc.get_meeting(session, meeting_id)
        return await reports.rename_participant(
            session, meeting_id, participant_id, body.display_name
        )


@router.get("/{meeting_id}/export/transcript.txt")
async def export_transcript(meeting_id: uuid.UUID, current: Current) -> Response:
    async with tenant_session(current.schema_name) as session:
        meeting = await svc.get_meeting(session, meeting_id)
        content = await reports.export_transcript(session, meeting_id)
        slug = reports.slugify(meeting.title)
    return _download(content, "text/plain; charset=utf-8", f"{slug}-transcript.txt")


@router.get("/{meeting_id}/export/recap.md")
async def export_recap(meeting_id: uuid.UUID, current: Current) -> Response:
    async with tenant_session(current.schema_name) as session:
        meeting = await svc.get_meeting(session, meeting_id)
        content = await reports.export_recap(session, meeting)
        slug = reports.slugify(meeting.title)
    return _download(content, "text/markdown; charset=utf-8", f"{slug}-recap.md")
