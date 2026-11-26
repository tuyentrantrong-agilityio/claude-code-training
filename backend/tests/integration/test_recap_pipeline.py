"""Transcribe and recap jobs plus the report read APIs, run through the worker."""

import json
import uuid
from pathlib import Path
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select, update

from app.core.settings import get_settings
from app.db.models.org import FollowUp, Job, Meeting, MeetingParticipant, TranscriptSegment
from app.db.session import tenant_session
from app.jobs import queue
from app.jobs.worker import Worker
from app.providers import registry
from app.providers.fakes import FakeBatchStt, FakeLlm
from app.providers.types import ChatMessage, LlmResult, Transcript
from tests.integration.conftest import FakeGoogle, make_org
from tests.integration.test_meetings import (  # noqa: F401  (autouse fixtures)
    MEETINGS,
    clean_jobs,
    jobs,
    make_meeting,
    make_wav,
    needs_ffmpeg,
    run_worker,
    signed_in,
    storage_dir,
    upload,
)

pytestmark = needs_ffmpeg
FOLLOW_UPS = "/api/v1/follow-ups"


class ScriptedLlm(FakeLlm):
    """Returns a fixed reply for recap prompts."""

    def __init__(self, reply: str) -> None:
        super().__init__()
        self.reply = reply

    async def complete(
        self, messages: list[ChatMessage], *, max_tokens: int, json_mode: bool = False
    ) -> LlmResult:
        return LlmResult(text=self.reply, input_tokens=10, output_tokens=5)


class EmptyStt(FakeBatchStt):
    async def transcribe(self, audio_path: Path, language: str) -> Transcript:
        return Transcript(language=language, duration_ms=0, segments=[])


def use_llm(monkeypatch: pytest.MonkeyPatch, reply: str) -> None:
    monkeypatch.setitem(registry._FACTORIES["llm"], "scripted", lambda: ScriptedLlm(reply))
    monkeypatch.setattr(get_settings(), "provider_llm", "scripted")


def use_stt(monkeypatch: pytest.MonkeyPatch, factory: Any) -> None:
    monkeypatch.setitem(registry._FACTORIES["stt_batch"], "custom", factory)
    monkeypatch.setattr(get_settings(), "provider_stt_batch", "custom")


async def process(client: AsyncClient, headers: dict[str, str], seconds: int = 8) -> str:
    """Upload a WAV and run decode, transcribe and recap; return the meeting id."""
    response = await upload(client, headers, make_wav(seconds), title="Release sync")
    assert response.status_code == 201
    await run_worker(3)
    return str(response.json()["id"])


async def make_due(schema: str) -> None:
    async with tenant_session(schema) as session:
        await session.execute(update(Job).where(Job.state == "queued").values(run_after=func.now()))


async def meeting_row(schema: str, meeting_id: str) -> Meeting:
    async with tenant_session(schema) as session:
        meeting = await session.get(Meeting, uuid.UUID(meeting_id))
        assert meeting is not None
        return meeting


async def test_full_pipeline_and_read_apis(client: AsyncClient, google: FakeGoogle) -> None:
    org, user_id, headers = await signed_in(client, google)
    meeting_id = await process(client, headers)
    base = f"{MEETINGS}/{meeting_id}"

    detail = (await client.get(base)).json()
    assert (detail["status"], detail["stage"], detail["error"]) == ("ready", None, None)
    assert detail["duration_ms"] is not None and 7900 <= detail["duration_ms"] <= 8100
    assert [p["display_name"] for p in detail["participants"]] == [
        "Speaker 1",
        "Speaker 2",
        "Speaker 3",
    ]
    assert detail["summary"] and detail["summary_preview"]
    assert [k for k, _ in await jobs(org.schema_name)] == ["decode", "transcribe", "recap"]

    # transcript
    segments = (await client.get(f"{base}/transcript")).json()["segments"]
    assert len(segments) == 8
    assert set(segments[0]) == {
        "id",
        "seq",
        "start_ms",
        "end_ms",
        "participant_id",
        "speaker",
        "text",
    }
    assert [s["seq"] for s in segments] == list(range(8))
    assert segments[0]["speaker"] == "Speaker 1" and segments[0]["start_ms"] == 0
    by_text = (await client.get(f"{base}/transcript", params={"q": "RELEASE NOTE"})).json()
    assert [s["text"] for s in by_text["segments"]] == ["I will send the release note today."]
    by_speaker = (await client.get(f"{base}/transcript", params={"q": "speaker 3"})).json()
    assert {s["speaker"] for s in by_speaker["segments"]} == {"Speaker 3"}
    for wildcard in ("%", "_", "\\"):
        none = await client.get(f"{base}/transcript", params={"q": wildcard})
        assert none.json() == {"segments": []}
    assert len((await client.get(f"{base}/transcript", params={"q": " "})).json()["segments"]) == 8

    # people
    people = (await client.get(f"{base}/people")).json()["people"]
    assert [set(p) for p in people] == [
        {"participant_id", "display_name", "speaker_label", "talk_ms", "share"}
    ] * 3
    assert [p["talk_ms"] for p in people] == sorted((p["talk_ms"] for p in people), reverse=True)
    assert abs(sum(p["share"] for p in people) - 1) < 1e-9
    assert people[0]["display_name"] == "Speaker 1" and people[0]["speaker_label"] == "Speaker 1"
    assert people[0]["talk_ms"] == 4 * 900

    # recap
    recap = (await client.get(f"{base}/recap")).json()
    assert set(recap) == {
        "summary",
        "summary_edited_at",
        "follow_ups",
        "key_points",
        "chapters",
        "highlights",
        "questions",
    }
    assert recap["summary"] == detail["summary"] and recap["summary_edited_at"] is None
    texts = [f["text"] for f in recap["follow_ups"]]
    assert "I will send the release note today." in texts and len(texts) == 4
    first = recap["follow_ups"][0]
    assert set(first) == {"id", "text", "owner_name", "owner_user_id", "at_ms", "state"}
    assert first["state"] == "open" and first["owner_user_id"] is None
    assert [f["at_ms"] for f in recap["follow_ups"]] == sorted(
        f["at_ms"] for f in recap["follow_ups"]
    )
    assert set(recap["key_points"][0]) == {"id", "title", "text", "at_ms"}
    assert set(recap["chapters"][0]) == {"id", "title", "at_ms"}
    assert set(recap["highlights"][0]) == {"id", "text", "at_ms"}
    assert [q["text"] for q in recap["questions"]] == [
        "Great. Can we ship it this week?",
        "What about the customer demo on Friday?",
    ]
    starts = {s["start_ms"] for s in segments}
    for kind in ("follow_ups", "key_points", "chapters", "highlights", "questions"):
        assert {i["at_ms"] for i in recap[kind]} <= starts

    # rename a speaker
    pid = people[0]["participant_id"]
    renamed = await client.patch(
        f"{base}/participants/{pid}", json={"display_name": "  Maya Chen  "}, headers=headers
    )
    assert renamed.status_code == 200
    assert renamed.json() == {
        "participant_id": pid,
        "display_name": "Maya Chen",
        "speaker_label": "Speaker 1",
    }
    assert "Maya Chen" in [
        p["display_name"] for p in (await client.get(base)).json()["participants"]
    ]
    by_new_name = (await client.get(f"{base}/transcript", params={"q": "maya"})).json()
    assert {s["speaker"] for s in by_new_name["segments"]} == {"Maya Chen"}
    for body in ({"display_name": ""}, {"display_name": "  "}, {"display_name": "x" * 81}, {}):
        bad = await client.patch(f"{base}/participants/{pid}", json=body, headers=headers)
        assert bad.status_code == 400 and bad.json()["error"]["code"] == "validation_error"
    no_csrf = await client.patch(f"{base}/participants/{pid}", json={"display_name": "A"})
    assert no_csrf.status_code == 403
    missing = await client.patch(
        f"{base}/participants/{uuid.uuid4()}", json={"display_name": "A"}, headers=headers
    )
    assert missing.status_code == 404 and missing.json()["error"]["code"] == "participant_not_found"

    # exports
    export = await client.get(f"{base}/export/transcript.txt")
    assert export.status_code == 200 and export.headers["content-type"].startswith("text/plain")
    assert (
        export.headers["content-disposition"]
        == 'attachment; filename="release-sync-transcript.txt"'
    )
    lines = export.text.splitlines()
    assert len(lines) == 8
    assert lines[0].startswith("[00:00] Maya Chen: Welcome everyone")
    assert lines[3] == "[00:03] Speaker 3: I will send the release note today."
    md = await client.get(f"{base}/export/recap.md")
    assert md.headers["content-type"].startswith("text/markdown")
    assert md.headers["content-disposition"] == 'attachment; filename="release-sync-recap.md"'
    assert md.text.startswith("# Release sync\n\nDate: ")
    for heading in ("## Summary", "## Follow-ups", "## Key points", "## Chapters"):
        assert heading in md.text
    assert "- [ ] I will send the release note today. (owner: Speaker 3) [00:03]" in md.text
    assert "- [00:00] " in md.text

    # usage was metered
    async with tenant_session(org.schema_name) as session:
        count = await session.scalar(select(func.count()).select_from(MeetingParticipant))
    assert count == 3 and user_id is not None


RECAP_REPLY = json.dumps(
    {
        "summary": "Short summary.",
        "follow_ups": [
            {"text": "Send the note", "owner": "ACME", "at_ms": 2500},
            {"text": "Ship it", "owner": "Somebody Else", "at_ms": 3999},
            {"text": "Beyond the end", "owner": "Acme", "at_ms": 999999},
            {"text": "Before the start", "owner": None, "at_ms": -5},
        ],
        "key_points": [{"text": "One two three four five six seven eight", "at_ms": 0}],
        "chapters": [{"title": "Intro", "at_ms": 0}, {"title": "Wrap", "at_ms": 7500}],
        "questions": [{"text": "Why?", "at_ms": 3999}],
    }
)


async def test_recap_validation_owner_match_and_follow_up_apis(
    client: AsyncClient, google: FakeGoogle, monkeypatch: pytest.MonkeyPatch
) -> None:
    org, user_id, headers = await signed_in(client, google)
    use_llm(monkeypatch, RECAP_REPLY)
    meeting_id = await process(client, headers)
    recap = (await client.get(f"{MEETINGS}/{meeting_id}/recap")).json()
    assert recap["summary"] == "Short summary."
    assert [(f["text"], f["at_ms"], f["owner_user_id"]) for f in recap["follow_ups"]] == [
        ("Send the note", 2000, str(user_id)),
        ("Ship it", 3000, None),
    ]
    assert recap["follow_ups"][1]["owner_name"] == "Somebody Else"
    assert [(k["title"], k["at_ms"]) for k in recap["key_points"]] == [
        ("One two three four five six", 0)
    ]
    assert [(c["title"], c["at_ms"]) for c in recap["chapters"]] == [("Intro", 0), ("Wrap", 7000)]
    assert recap["highlights"] == []
    assert [(q["text"], q["at_ms"]) for q in recap["questions"]] == [("Why?", 3000)]

    mine = (await client.get(FOLLOW_UPS, params={"owner": "me"})).json()["items"]
    assert [i["text"] for i in mine] == ["Send the note"]
    assert set(mine[0]) == {
        "id",
        "text",
        "owner_name",
        "owner_user_id",
        "at_ms",
        "state",
        "meeting_id",
        "meeting_title",
    }
    assert (mine[0]["meeting_id"], mine[0]["meeting_title"]) == (meeting_id, "Release sync")
    assert len((await client.get(FOLLOW_UPS, params={"owner": "all"})).json()["items"]) == 2
    assert len((await client.get(FOLLOW_UPS)).json()["items"]) == 2
    assert (await client.get(f"{FOLLOW_UPS}/count")).json() == {"open_mine": 1}

    follow_id = mine[0]["id"]
    assert (
        await client.patch(f"{FOLLOW_UPS}/{follow_id}", json={"state": "done"})
    ).status_code == 403
    for body in ({"state": "later"}, {}):
        bad = await client.patch(f"{FOLLOW_UPS}/{follow_id}", json=body, headers=headers)
        assert bad.status_code == 400
    done = await client.patch(f"{FOLLOW_UPS}/{follow_id}", json={"state": "done"}, headers=headers)
    assert done.status_code == 200 and done.json()["state"] == "done"
    assert done.json()["meeting_title"] == "Release sync"
    async with tenant_session(org.schema_name) as session:
        row = await session.get(FollowUp, uuid.UUID(follow_id))
        assert row is not None and row.done_at is not None
    assert (await client.get(f"{FOLLOW_UPS}/count")).json() == {"open_mine": 0}
    done_list = (await client.get(FOLLOW_UPS, params={"state": "done"})).json()["items"]
    assert [i["id"] for i in done_list] == [follow_id]
    open_all = (await client.get(FOLLOW_UPS, params={"owner": "all", "state": "open"})).json()
    assert [i["text"] for i in open_all["items"]] == ["Ship it"]
    assert (await client.get(FOLLOW_UPS, params={"owner": "me", "state": "open"})).json() == {
        "items": []
    }
    reopened = await client.patch(
        f"{FOLLOW_UPS}/{follow_id}", json={"state": "open"}, headers=headers
    )
    assert reopened.json()["state"] == "open"
    async with tenant_session(org.schema_name) as session:
        row = await session.get(FollowUp, uuid.UUID(follow_id))
        assert row is not None and row.done_at is None
    assert (await client.get(f"{FOLLOW_UPS}/count")).json() == {"open_mine": 1}
    assert (await client.get(FOLLOW_UPS, params={"owner": "x"})).status_code == 400


async def test_follow_ups_skip_unfinished_deleted_and_other_org(
    client: AsyncClient, google: FakeGoogle, monkeypatch: pytest.MonkeyPatch
) -> None:
    org, user_id, headers = await signed_in(client, google)
    use_llm(monkeypatch, RECAP_REPLY)
    meeting_id = await process(client, headers)
    assert (await client.get(f"{FOLLOW_UPS}/count")).json() == {"open_mine": 1}
    async with tenant_session(org.schema_name) as session:
        await session.execute(
            update(Meeting).where(Meeting.status == "ready").values(status="processing")
        )
    assert (await client.get(FOLLOW_UPS)).json() == {"items": []}
    assert (await client.get(f"{FOLLOW_UPS}/count")).json() == {"open_mine": 0}
    async with tenant_session(org.schema_name) as session:
        await session.execute(update(Meeting).values(status="ready"))
    assert len((await client.get(FOLLOW_UPS)).json()["items"]) == 2
    assert (await client.delete(f"{MEETINGS}/{meeting_id}", headers=headers)).status_code == 204
    assert (await client.get(FOLLOW_UPS)).json() == {"items": []}

    other = await make_org("Other")
    other_meeting = await make_meeting(other.schema_name, "Secret")
    async with tenant_session(other.schema_name) as session:
        foreign = FollowUp(meeting_id=other_meeting, text="Hidden", owner_user_id=user_id)
        session.add(foreign)
        await session.flush()
        foreign_id = foreign.id
    assert (await client.get(FOLLOW_UPS)).json() == {"items": []}
    patched = await client.patch(
        f"{FOLLOW_UPS}/{foreign_id}", json={"state": "done"}, headers=headers
    )
    assert patched.status_code == 404 and patched.json()["error"]["code"] == "follow_up_not_found"
    for path in ("recap", "transcript", "people", "export/transcript.txt", "export/recap.md"):
        response = await client.get(f"{MEETINGS}/{other_meeting}/{path}")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "meeting_not_found"
    rename = await client.patch(
        f"{MEETINGS}/{other_meeting}/participants/{uuid.uuid4()}",
        json={"display_name": "A"},
        headers=headers,
    )
    assert rename.status_code == 404 and rename.json()["error"]["code"] == "meeting_not_found"


async def test_read_apis_need_sign_in(client: AsyncClient) -> None:
    mid = uuid.uuid4()
    for path in (
        f"{MEETINGS}/{mid}/recap",
        f"{MEETINGS}/{mid}/transcript",
        f"{MEETINGS}/{mid}/people",
        f"{MEETINGS}/{mid}/export/recap.md",
        FOLLOW_UPS,
        f"{FOLLOW_UPS}/count",
    ):
        assert (await client.get(path)).status_code == 401


async def test_recap_retry_keeps_user_edits_and_done_follow_ups(
    client: AsyncClient, google: FakeGoogle
) -> None:
    org, _, headers = await signed_in(client, google)
    meeting_id = await process(client, headers)
    base = f"{MEETINGS}/{meeting_id}"
    edited = await client.patch(base, json={"summary": "My own words."}, headers=headers)
    stamp = edited.json()["summary_edited_at"]
    before = (await client.get(f"{base}/recap")).json()
    done_id = before["follow_ups"][0]["id"]
    await client.patch(f"{FOLLOW_UPS}/{done_id}", json={"state": "done"}, headers=headers)

    async with tenant_session(org.schema_name) as session:
        await queue.enqueue(session, "recap", uuid.UUID(meeting_id))
    await run_worker()
    after = (await client.get(f"{base}/recap")).json()
    assert after["summary"] == "My own words." and after["summary_edited_at"] == stamp
    assert len(after["follow_ups"]) == len(before["follow_ups"])  # no duplicates
    kept = next(f for f in after["follow_ups"] if f["id"] == done_id)
    assert kept["state"] == "done"
    assert [i["text"] for i in after["key_points"]] == [i["text"] for i in before["key_points"]]
    detail = (await client.get(base)).json()
    assert (detail["status"], detail["stage"]) == ("ready", None)


async def test_transcribe_again_replaces_transcript(
    client: AsyncClient, google: FakeGoogle
) -> None:
    org, _, headers = await signed_in(client, google)
    meeting_id = await process(client, headers)
    async with tenant_session(org.schema_name) as session:
        await queue.enqueue(session, "transcribe", uuid.UUID(meeting_id))
    await run_worker()
    assert (await client.get(f"{MEETINGS}/{meeting_id}")).json()["stage"] == "summarizing"
    async with tenant_session(org.schema_name) as session:
        segments = await session.scalar(select(func.count()).select_from(TranscriptSegment))
        people = await session.scalar(select(func.count()).select_from(MeetingParticipant))
    assert (segments, people) == (8, 3)
    await run_worker()
    assert (await client.get(f"{MEETINGS}/{meeting_id}")).json()["status"] == "ready"


async def test_empty_transcript_is_ready_without_recap(
    client: AsyncClient, google: FakeGoogle, monkeypatch: pytest.MonkeyPatch
) -> None:
    org, _, headers = await signed_in(client, google)
    use_stt(monkeypatch, EmptyStt)
    meeting_id = await process(client, headers)
    detail = (await client.get(f"{MEETINGS}/{meeting_id}")).json()
    assert (detail["status"], detail["stage"], detail["error"]) == ("ready", None, None)
    assert detail["summary"] == "No speech was detected in this recording."
    assert detail["participants"] == []
    assert await jobs(org.schema_name) == [("decode", "succeeded"), ("transcribe", "succeeded")]
    recap = (await client.get(f"{MEETINGS}/{meeting_id}/recap")).json()
    assert recap["follow_ups"] == [] and recap["key_points"] == []
    assert (await client.get(f"{MEETINGS}/{meeting_id}/transcript")).json() == {"segments": []}
    assert (await client.get(f"{MEETINGS}/{meeting_id}/people")).json() == {"people": []}
    assert (await client.get(f"{MEETINGS}/{meeting_id}/export/transcript.txt")).text == ""


async def test_invalid_recap_json_retries_once_then_incomplete(
    client: AsyncClient, google: FakeGoogle, monkeypatch: pytest.MonkeyPatch
) -> None:
    org, _, headers = await signed_in(client, google)
    use_llm(monkeypatch, "this is not json")
    meeting_id = await process(client, headers)
    detail = (await client.get(f"{MEETINGS}/{meeting_id}")).json()
    assert (detail["status"], detail["stage"], detail["error"]) == (
        "processing",
        "summarizing",
        None,
    )
    assert (await jobs(org.schema_name))[-1] == ("recap", "queued")  # waiting to retry

    await make_due(org.schema_name)
    await run_worker()
    detail = (await client.get(f"{MEETINGS}/{meeting_id}")).json()
    assert (detail["status"], detail["stage"]) == ("incomplete", "summarizing")
    assert detail["error"] == "Could not generate the recap."
    assert (await jobs(org.schema_name))[-1] == ("recap", "failed")
    async with tenant_session(org.schema_name) as session:
        attempts = await session.scalar(select(Job.attempts).where(Job.kind == "recap"))
    assert attempts == 2

    # Retrying the stage with a good reply finishes the meeting.
    use_llm(monkeypatch, RECAP_REPLY)
    retry = await client.post(f"{MEETINGS}/{meeting_id}/retry", headers=headers)
    assert retry.status_code == 200
    await run_worker()
    assert (await client.get(f"{MEETINGS}/{meeting_id}")).json()["status"] == "ready"


async def test_llm_provider_error_marks_incomplete(
    client: AsyncClient, google: FakeGoogle, monkeypatch: pytest.MonkeyPatch
) -> None:
    org, _, headers = await signed_in(client, google)
    monkeypatch.setitem(
        registry._FACTORIES["llm"], "down", lambda: FakeLlm(fail_times=9, retryable=False)
    )
    monkeypatch.setattr(get_settings(), "provider_llm", "down")
    meeting_id = await process(client, headers)
    detail = (await client.get(f"{MEETINGS}/{meeting_id}")).json()
    assert (detail["status"], detail["error"]) == ("incomplete", "Could not generate the recap.")
    assert (await jobs(org.schema_name))[-1] == ("recap", "failed")


async def test_non_retryable_stt_error_marks_incomplete(
    client: AsyncClient, google: FakeGoogle, monkeypatch: pytest.MonkeyPatch
) -> None:
    org, _, headers = await signed_in(client, google)
    use_stt(monkeypatch, lambda: FakeBatchStt(fail_times=1, retryable=False))
    meeting_id = await process(client, headers)
    detail = (await client.get(f"{MEETINGS}/{meeting_id}")).json()
    assert (detail["status"], detail["stage"]) == ("incomplete", "transcribing")
    assert detail["error"] == "Transcription failed."
    assert (await jobs(org.schema_name))[-1] == ("transcribe", "failed")
    assert (await client.get(f"{MEETINGS}/{meeting_id}/transcript")).json() == {"segments": []}


async def test_retryable_stt_error_retries_then_gives_up(
    client: AsyncClient, google: FakeGoogle, monkeypatch: pytest.MonkeyPatch
) -> None:
    org, _, headers = await signed_in(client, google)
    monkeypatch.setattr(get_settings(), "provider_max_retries", 0)
    use_stt(monkeypatch, lambda: FakeBatchStt(fail_times=99, retryable=True))
    response = await upload(client, headers, make_wav(2))
    meeting_id = response.json()["id"]
    worker = Worker(max_attempts=2)
    await worker.run_once()  # decode
    await worker.run_once()  # transcribe, attempt 1
    detail = (await client.get(f"{MEETINGS}/{meeting_id}")).json()
    assert (detail["status"], detail["stage"], detail["error"]) == (
        "processing",
        "transcribing",
        None,
    )
    await make_due(org.schema_name)
    await worker.run_once()  # attempt 2 is the last
    detail = (await client.get(f"{MEETINGS}/{meeting_id}")).json()
    assert (detail["status"], detail["error"]) == ("incomplete", "Transcription failed.")
    assert (await jobs(org.schema_name))[-1] == ("transcribe", "failed")
