import asyncio
import io
import json
import shutil
import uuid
import wave
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import delete, select

from app.core.settings import get_settings
from app.db.models.org import Job, Meeting, MeetingParticipant, Recording
from app.db.models.public import Organization
from app.db.session import get_sessionmaker, tenant_session
from app.jobs.worker import Worker
from tests.integration.conftest import (
    FakeGoogle,
    add_member,
    csrf_headers,
    make_org,
    sign_in,
)

needs_ffmpeg = pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="ffmpeg and ffprobe are not installed",
)
UPLOADS = "/api/v1/meetings/uploads"
MEETINGS = "/api/v1/meetings"


@pytest.fixture(autouse=True)
def storage_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    settings = get_settings()
    monkeypatch.setattr(settings, "storage_dir", str(tmp_path / "recordings"))
    monkeypatch.setattr(settings, "sse_poll_interval_seconds", 0.05)
    return tmp_path / "recordings"


@pytest.fixture(autouse=True)
async def clean_jobs() -> None:
    async with get_sessionmaker()() as session:
        schemas = list(await session.scalars(select(Organization.schema_name)))
    for schema in schemas:
        async with tenant_session(schema) as session:
            await session.execute(delete(Job))


def make_wav(seconds: int = 1, rate: int = 8000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\x00\x10" * rate * seconds)
    return buf.getvalue()


async def signed_in(client: AsyncClient, google: FakeGoogle, org_name: str = "Acme"):  # type: ignore[no-untyped-def]
    org = await make_org(org_name)
    user_id = await add_member(org, f"{org_name.lower()}@example.com", "member")
    await sign_in(client, google, f"{org_name.lower()}@example.com")
    return org, user_id, await csrf_headers(client)


async def upload(
    client: AsyncClient,
    headers: dict[str, str],
    data: bytes | None = None,
    name: str = "weekly sync.wav",
    **form: str,
):  # type: ignore[no-untyped-def]
    return await client.post(
        UPLOADS,
        files={"file": (name, make_wav() if data is None else data, "audio/wav")},
        data=form,
        headers=headers,
    )


async def jobs(schema: str) -> list[tuple[str, str]]:
    async with tenant_session(schema) as session:
        rows = await session.execute(select(Job.kind, Job.state).order_by(Job.created_at))
        return [(k, s) for k, s in rows]


async def run_worker(times: int = 1) -> None:
    for _ in range(times):
        await Worker().run_once()


# ---- upload ----


@needs_ffmpeg
async def test_upload_decode_and_ready(
    client: AsyncClient, google: FakeGoogle, storage_dir: Path
) -> None:
    org, user_id, headers = await signed_in(client, google)
    response = await upload(client, headers, language="vi")
    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "weekly sync"
    assert (body["status"], body["stage"], body["source"], body["platform"]) == (
        "processing",
        "uploading",
        "upload",
        "file",
    )
    assert body["language"] == "vi" and body["participants"] == [] and body["folder"] is None
    meeting_id = uuid.UUID(body["id"])
    assert await jobs(org.schema_name) == [("decode", "queued")]
    async with tenant_session(org.schema_name) as session:
        meeting = await session.get(Meeting, meeting_id)
        recording = await session.scalar(select(Recording))
    assert meeting is not None and meeting.owner_id == user_id
    assert recording is not None and recording.mime_type == "audio/wav"
    assert recording.size_bytes == len(make_wav())
    assert recording.original_path == f"{org.schema_name}/{meeting_id}/original.wav"
    assert (storage_dir / recording.original_path).is_file()

    await run_worker()
    detail = (await client.get(f"{MEETINGS}/{meeting_id}")).json()
    assert detail["duration_ms"] is not None and 900 <= detail["duration_ms"] <= 1100
    assert (detail["status"], detail["stage"]) == ("processing", "transcribing")
    assert (storage_dir / org.schema_name / str(meeting_id) / "audio.wav").is_file()
    assert await jobs(org.schema_name) == [("decode", "succeeded"), ("transcribe", "queued")]

    await run_worker()
    detail = (await client.get(f"{MEETINGS}/{meeting_id}")).json()
    assert (detail["status"], detail["stage"]) == ("ready", None)


async def test_upload_defaults_and_title(client: AsyncClient, google: FakeGoogle) -> None:
    _, _, headers = await signed_in(client, google)
    body = (await upload(client, headers, title="  My title  ", name="a.MP3")).json()
    assert body["title"] == "My title" and body["language"] == "en"


async def test_upload_rejects_bad_type_and_language(
    client: AsyncClient, google: FakeGoogle, storage_dir: Path
) -> None:
    org, _, headers = await signed_in(client, google)
    bad = await upload(client, headers, b"hello", name="notes.txt")
    assert bad.status_code == 400 and bad.json()["error"]["code"] == "unsupported_file_type"
    noext = await upload(client, headers, b"hello", name="noext")
    assert noext.json()["error"]["code"] == "unsupported_file_type"
    lang = await upload(client, headers, language="fr")
    assert lang.status_code == 400 and lang.json()["error"]["code"] == "validation_error"
    assert await jobs(org.schema_name) == []
    assert not storage_dir.exists() or list(storage_dir.rglob("*.*")) == []


async def test_upload_too_large(
    client: AsyncClient,
    google: FakeGoogle,
    storage_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    org, _, headers = await signed_in(client, google)
    monkeypatch.setattr(get_settings(), "max_upload_mb", 0.001)
    response = await upload(client, headers, make_wav(1))
    assert response.status_code == 413 and response.json()["error"]["code"] == "file_too_large"
    assert await jobs(org.schema_name) == []
    assert not storage_dir.exists() or list(storage_dir.rglob("*.*")) == []
    async with tenant_session(org.schema_name) as session:
        assert (await session.scalars(select(Meeting))).all() == []


async def test_upload_needs_session_and_csrf(client: AsyncClient, google: FakeGoogle) -> None:
    assert (await upload(client, {})).status_code == 401
    await signed_in(client, google)
    response = await upload(client, {})
    assert response.status_code == 403 and response.json()["error"]["code"] == "csrf_failed"


# ---- list, get, patch, delete ----


async def make_meeting(
    schema: str, title: str, status: str = "ready", minutes: int = 0
) -> uuid.UUID:
    async with tenant_session(schema) as session:
        meeting = Meeting(
            title=title,
            source="upload",
            platform="file",
            language="en",
            status=status,
            started_at=datetime(2026, 11, 1, tzinfo=UTC) + timedelta(minutes=minutes),
        )
        session.add(meeting)
        await session.flush()
        return meeting.id


async def test_list_filters_counts_and_paging(client: AsyncClient, google: FakeGoogle) -> None:
    org, _, _ = await signed_in(client, google)
    s = org.schema_name
    ids = [
        await make_meeting(s, "Alpha plan", "ready", 1),
        await make_meeting(s, "Beta 100%", "ready", 2),
        await make_meeting(s, "Gamma plan", "incomplete", 3),
        await make_meeting(s, "Delta", "processing", 4),
    ]
    async with tenant_session(s) as session:
        meeting = await session.get(Meeting, ids[0])
        assert meeting is not None
        session.add(MeetingParticipant(meeting_id=ids[0], display_name="Maya Chen"))
        gone = Meeting(
            title="Removed", source="upload", platform="file", language="en", status="ready"
        )
        gone.deleted_at = meeting.created_at
        session.add(gone)

    everything = (await client.get(MEETINGS)).json()
    assert [i["title"] for i in everything["items"]] == [
        "Delta",
        "Gamma plan",
        "Beta 100%",
        "Alpha plan",
    ]
    assert everything["meta"]["counts"] == {"processing": 1, "ready": 2, "incomplete": 1}
    assert everything["next_cursor"] is None
    assert everything["items"][3]["participants"][0]["display_name"] == "Maya Chen"

    ready = (await client.get(MEETINGS, params={"status": "ready"})).json()
    assert [i["title"] for i in ready["items"]] == ["Beta 100%", "Alpha plan"]
    assert ready["meta"]["counts"]["incomplete"] == 1

    found = (await client.get(MEETINGS, params={"q": "PLAN"})).json()
    assert [i["title"] for i in found["items"]] == ["Gamma plan", "Alpha plan"]
    assert found["meta"]["counts"] == {"processing": 0, "ready": 1, "incomplete": 1}
    percent = (await client.get(MEETINGS, params={"q": "%"})).json()
    assert [i["title"] for i in percent["items"]] == ["Beta 100%"]

    first = (await client.get(MEETINGS, params={"limit": 3})).json()
    assert len(first["items"]) == 3 and first["next_cursor"]
    second = (
        await client.get(MEETINGS, params={"limit": 3, "cursor": first["next_cursor"]})
    ).json()
    assert [i["title"] for i in second["items"]] == ["Alpha plan"]
    assert second["next_cursor"] is None

    bad = await client.get(MEETINGS, params={"cursor": "nope"})
    assert bad.status_code == 400
    assert (await client.get(MEETINGS, params={"limit": 101})).status_code == 400
    assert (await client.get(MEETINGS, params={"status": "weird"})).status_code == 400


async def test_get_patch_and_other_org(client: AsyncClient, google: FakeGoogle) -> None:
    org, _, headers = await signed_in(client, google)
    meeting_id = await make_meeting(org.schema_name, "Old title")
    detail = (await client.get(f"{MEETINGS}/{meeting_id}")).json()
    assert detail["title"] == "Old title" and detail["summary"] is None
    assert detail["summary_edited_at"] is None

    no_csrf = await client.patch(f"{MEETINGS}/{meeting_id}", json={"title": "x"})
    assert no_csrf.status_code == 403
    renamed = await client.patch(
        f"{MEETINGS}/{meeting_id}", json={"title": " New title "}, headers=headers
    )
    assert renamed.json()["title"] == "New title" and renamed.json()["summary_edited_at"] is None
    edited = await client.patch(
        f"{MEETINGS}/{meeting_id}", json={"summary": "We agreed."}, headers=headers
    )
    assert edited.json()["summary"] == "We agreed." and edited.json()["summary_edited_at"]
    assert edited.json()["summary_preview"] == "We agreed."
    for body in ({}, {"title": "  "}):
        bad = await client.patch(f"{MEETINGS}/{meeting_id}", json=body, headers=headers)
        assert bad.status_code == 400

    other = await make_org("Other")
    other_meeting = await make_meeting(other.schema_name, "Secret")
    for response in (
        await client.get(f"{MEETINGS}/{other_meeting}"),
        await client.patch(f"{MEETINGS}/{other_meeting}", json={"title": "x"}, headers=headers),
        await client.delete(f"{MEETINGS}/{other_meeting}", headers=headers),
        await client.post(f"{MEETINGS}/{other_meeting}/retry", headers=headers),
        await client.get(f"{MEETINGS}/{other_meeting}/audio"),
        await client.get(f"{MEETINGS}/{other_meeting}/events"),
        await client.get(f"{MEETINGS}/{uuid.uuid4()}"),
    ):
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "meeting_not_found"
    listed = (await client.get(MEETINGS)).json()
    assert [i["title"] for i in listed["items"]] == ["New title"]


async def test_meetings_need_sign_in(client: AsyncClient) -> None:
    assert (await client.get(MEETINGS)).status_code == 401
    assert (await client.get(f"{MEETINGS}/{uuid.uuid4()}/audio")).status_code == 401


@needs_ffmpeg
async def test_delete_removes_rows_and_files(
    client: AsyncClient, google: FakeGoogle, storage_dir: Path
) -> None:
    org, _, headers = await signed_in(client, google)
    meeting_id = (await upload(client, headers)).json()["id"]
    await run_worker()
    folder = storage_dir / org.schema_name / meeting_id
    assert {p.name for p in folder.iterdir()} == {"original.wav", "audio.wav"}
    assert (await client.delete(f"{MEETINGS}/{meeting_id}")).status_code == 403
    assert (await client.delete(f"{MEETINGS}/{meeting_id}", headers=headers)).status_code == 204
    assert not folder.exists()
    assert (await client.get(f"{MEETINGS}/{meeting_id}")).status_code == 404
    assert (await client.delete(f"{MEETINGS}/{meeting_id}", headers=headers)).status_code == 404
    async with tenant_session(org.schema_name) as session:
        assert (await session.scalars(select(Recording))).all() == []
        assert (await session.scalars(select(Job))).all() == []


# ---- retry ----


@needs_ffmpeg
async def test_corrupt_upload_becomes_incomplete_and_retry(
    client: AsyncClient, google: FakeGoogle
) -> None:
    org, _, headers = await signed_in(client, google)
    meeting_id = (await upload(client, headers, b"this is not audio", name="bad.wav")).json()["id"]
    await run_worker()
    detail = (await client.get(f"{MEETINGS}/{meeting_id}")).json()
    assert detail["status"] == "incomplete"
    assert detail["error"] == "Could not read the audio in this file."
    assert detail["stage"] == "uploading"
    assert await jobs(org.schema_name) == [("decode", "failed")]  # no retries
    assert (await client.get(f"{MEETINGS}/{meeting_id}/audio")).status_code == 404

    assert (await client.post(f"{MEETINGS}/{meeting_id}/retry")).status_code == 403
    retried = await client.post(f"{MEETINGS}/{meeting_id}/retry", headers=headers)
    assert retried.status_code == 200
    assert (retried.json()["status"], retried.json()["error"]) == ("processing", None)
    assert await jobs(org.schema_name) == [("decode", "failed"), ("decode", "queued")]
    again = await client.post(f"{MEETINGS}/{meeting_id}/retry", headers=headers)
    assert again.status_code == 409 and again.json()["error"]["code"] == "stage_already_running"


async def test_retry_ready_meeting_is_refused(client: AsyncClient, google: FakeGoogle) -> None:
    org, _, headers = await signed_in(client, google)
    meeting_id = await make_meeting(org.schema_name, "Done", "ready")
    response = await client.post(f"{MEETINGS}/{meeting_id}/retry", headers=headers)
    assert response.status_code == 409 and response.json()["error"]["code"] == "not_retryable"


async def test_retry_transcribing_stage_enqueues_transcribe(
    client: AsyncClient, google: FakeGoogle
) -> None:
    org, _, headers = await signed_in(client, google)
    meeting_id = await make_meeting(org.schema_name, "Stuck", "incomplete")
    async with tenant_session(org.schema_name) as session:
        meeting = await session.get(Meeting, meeting_id)
        assert meeting is not None
        meeting.stage = "transcribing"
    response = await client.post(f"{MEETINGS}/{meeting_id}/retry", headers=headers)
    assert response.status_code == 200 and response.json()["stage"] == "transcribing"
    assert await jobs(org.schema_name) == [("transcribe", "queued")]


# ---- audio ----


@needs_ffmpeg
async def test_audio_range(client: AsyncClient, google: FakeGoogle, storage_dir: Path) -> None:
    org, _, headers = await signed_in(client, google)
    meeting_id = (await upload(client, headers)).json()["id"]
    assert (await client.get(f"{MEETINGS}/{meeting_id}/audio")).status_code == 404
    await run_worker()
    on_disk = (storage_dir / org.schema_name / meeting_id / "audio.wav").read_bytes()
    full = await client.get(f"{MEETINGS}/{meeting_id}/audio")
    assert full.status_code == 200 and full.content == on_disk
    assert full.headers["accept-ranges"] == "bytes"
    assert full.headers["content-type"] == "audio/wav"
    assert on_disk[:4] == b"RIFF" and len(on_disk) > 30000  # 16 kHz mono 16-bit, 1 s

    part = await client.get(f"{MEETINGS}/{meeting_id}/audio", headers={"Range": "bytes=100-199"})
    assert part.status_code == 206 and part.content == on_disk[100:200]
    assert part.headers["content-range"] == f"bytes 100-199/{len(on_disk)}"
    assert part.headers["content-length"] == "100"
    tail = await client.get(f"{MEETINGS}/{meeting_id}/audio", headers={"Range": "bytes=-50"})
    assert tail.status_code == 206 and tail.content == on_disk[-50:]
    open_end = await client.get(f"{MEETINGS}/{meeting_id}/audio", headers={"Range": "bytes=40-"})
    assert open_end.content == on_disk[40:]
    past = await client.get(
        f"{MEETINGS}/{meeting_id}/audio", headers={"Range": f"bytes={len(on_disk)}-"}
    )
    assert past.status_code == 416
    assert past.headers["content-range"] == f"bytes */{len(on_disk)}"


# ---- events ----


async def read_events(client: AsyncClient, meeting_id: str) -> list[tuple[str, dict[str, object]]]:
    events: list[tuple[str, dict[str, object]]] = []
    name = ""
    async with client.stream("GET", f"{MEETINGS}/{meeting_id}/events") as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        async for line in response.aiter_lines():
            if line.startswith("event: "):
                name = line[7:]
            elif line.startswith("data: "):
                events.append((name, json.loads(line[6:])))
    return events


@needs_ffmpeg
async def test_events_stream_until_ready(client: AsyncClient, google: FakeGoogle) -> None:
    _, _, headers = await signed_in(client, google)
    meeting_id = (await upload(client, headers)).json()["id"]

    async def drive() -> None:
        for _ in range(2):
            await asyncio.sleep(0.3)
            await run_worker()

    driver = asyncio.create_task(drive())
    events = await asyncio.wait_for(read_events(client, meeting_id), timeout=30)
    await driver
    assert events[0] == ("stage", {"stage": "uploading"})
    assert ("stage", {"stage": "transcribing"}) in events
    assert events[-2] == ("stage", {"stage": None})
    assert events[-1] == ("status", {"status": "ready", "error": None})


async def test_events_end_immediately_when_finished(
    client: AsyncClient, google: FakeGoogle
) -> None:
    org, _, _ = await signed_in(client, google)
    meeting_id = await make_meeting(org.schema_name, "Done", "ready")
    events = await read_events(client, str(meeting_id))
    assert events == [
        ("stage", {"stage": None}),
        ("status", {"status": "ready", "error": None}),
    ]


async def test_events_stop_after_max_seconds(
    client: AsyncClient, google: FakeGoogle, monkeypatch: pytest.MonkeyPatch
) -> None:
    org, _, _ = await signed_in(client, google)
    meeting_id = await make_meeting(org.schema_name, "Busy", "processing")
    monkeypatch.setattr(get_settings(), "sse_max_seconds", 0.2)
    events = await asyncio.wait_for(read_events(client, str(meeting_id)), timeout=10)
    assert [e[0] for e in events] == ["stage", "status"]
