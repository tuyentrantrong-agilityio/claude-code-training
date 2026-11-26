"""Search index job, hybrid retrieval, Ask API (SSE) and Home API."""

import json
import uuid
from datetime import UTC, datetime, timedelta
from functools import partial

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import func, select, text, update

from app.core.settings import get_settings
from app.db.models.org import (
    Citation,
    FollowUp,
    Job,
    Meeting,
    MeetingParticipant,
    Message,
    SearchChunk,
    TranscriptSegment,
    UsageEvent,
)
from app.db.session import tenant_session
from app.jobs import queue
from app.jobs.handlers.index import INDEX_ERROR
from app.jobs.registry import JobContext, dispatch
from app.jobs.worker import Worker
from app.providers import registry
from app.providers.fakes import FakeEmbedding, FakeLlm
from app.services import ask
from tests.integration.conftest import FakeGoogle, add_member, make_org, sign_in, use_session
from tests.integration.test_meetings import (  # noqa: F401  (autouse fixtures)
    MEETINGS,
    clean_jobs,
    jobs,
    make_wav,
    needs_ffmpeg,
    run_worker,
    signed_in,
    storage_dir,
    upload,
)

CONVERSATIONS = "/api/v1/conversations"
HOME = "/api/v1/home"
NOT_FOUND = (
    "I could not find that in your meetings. Try different words, or ask across all meetings."
)

PLANNING = [
    ("Maya", "We should budget for the quarterly offsite in Lisbon."),
    ("Noah", "Marketing wants the zebra campaign finished before launch."),
]
RELEASE = [
    ("Maya", "The release candidate passed every regression test."),
    ("Noah", "Rollback plan is documented in the wiki."),
]


async def make_indexed(
    schema: str,
    title: str,
    lines: list[tuple[str, str]],
    *,
    status: str = "ready",
    minutes: int = 0,
    gap_ms: int = 1000,
) -> uuid.UUID:
    """A meeting with a transcript; chunks come from the real index handler."""
    async with tenant_session(schema) as session:
        meeting = Meeting(
            title=title,
            source="upload",
            platform="file",
            language="en",
            status="processing",
            stage="filing",
            started_at=datetime(2026, 11, 1, tzinfo=UTC) + timedelta(minutes=minutes),
        )
        session.add(meeting)
        await session.flush()
        people: dict[str, MeetingParticipant] = {}
        for name, _ in lines:
            if name not in people:
                people[name] = MeetingParticipant(meeting_id=meeting.id, display_name=name)
        session.add_all(people.values())
        await session.flush()
        for seq, (name, said) in enumerate(lines):
            session.add(
                TranscriptSegment(
                    meeting_id=meeting.id,
                    seq=seq,
                    start_ms=seq * gap_ms,
                    end_ms=seq * gap_ms + 500,
                    participant_id=people[name].id,
                    text=said,
                )
            )
        await session.flush()
        meeting_id = meeting.id
    await run_index(schema, meeting_id)
    if status != "ready":
        async with tenant_session(schema) as session:
            await session.execute(
                update(Meeting).where(Meeting.id == meeting_id).values(status=status)
            )
    return meeting_id


async def run_index(schema: str, meeting_id: uuid.UUID) -> None:
    ctx = JobContext(
        schema_name=schema,
        job_id=uuid.uuid4(),
        meeting_id=meeting_id,
        session_factory=partial(tenant_session, schema),
    )
    await dispatch("index", ctx)


def parse_sse(response: Response) -> list[tuple[str, dict[str, object]]]:
    events: list[tuple[str, dict[str, object]]] = []
    for block in response.text.split("\n\n"):
        if not block.strip():
            continue
        name, data = block.split("\n", 1)
        assert name.startswith("event: ") and data.startswith("data: ")
        events.append((name[7:], json.loads(data[6:])))
    return events


async def new_conversation(
    client: AsyncClient, headers: dict[str, str], scope: str | None = None
) -> str:
    response = await client.post(CONVERSATIONS, json={"scope_meeting_id": scope}, headers=headers)
    assert response.status_code == 201
    return str(response.json()["id"])


async def ask_question(
    client: AsyncClient, headers: dict[str, str], conversation_id: str, question: str
) -> Response:
    return await client.post(
        f"{CONVERSATIONS}/{conversation_id}/messages", json={"text": question}, headers=headers
    )


def use_llm(monkeypatch: pytest.MonkeyPatch, llm: FakeLlm) -> FakeLlm:
    monkeypatch.setitem(registry._FACTORIES["llm"], "shared", lambda: llm)
    monkeypatch.setattr(get_settings(), "provider_llm", "shared")
    return llm


# ---- index job ----


@needs_ffmpeg
async def test_pipeline_ends_with_index_and_chunks(client: AsyncClient, google: FakeGoogle) -> None:
    org, _, headers = await signed_in(client, google)
    meeting_id = (await upload(client, headers, make_wav(8), title="Release sync")).json()["id"]
    await run_worker(4)
    detail = (await client.get(f"{MEETINGS}/{meeting_id}")).json()
    assert (detail["status"], detail["stage"], detail["error"]) == ("ready", None, None)
    assert [k for k, _ in await jobs(org.schema_name)] == [
        "decode",
        "transcribe",
        "recap",
        "index",
    ]
    async with tenant_session(org.schema_name) as session:
        rows = (
            await session.execute(
                text(
                    "SELECT seq, start_ms, end_ms, text, tsv IS NOT NULL, "
                    "vector_dims(embedding) FROM search_chunks"
                )
            )
        ).all()
        usage = await session.scalar(
            select(func.count()).select_from(UsageEvent).where(UsageEvent.function == "embedding")
        )
    assert len(rows) == 1  # eight short lines fit into one chunk
    seq, start, end, body, has_tsv, dims = rows[0]
    assert (seq, start, has_tsv, dims) == (0, 0, True, 8)
    assert end > start and body.startswith("Speaker 1: Welcome everyone")
    assert body.count("\n") == 7 and "Speaker 3: I will send the release note today." in body
    assert usage == 1


async def test_index_replaces_chunks_and_empty_transcript_is_ready() -> None:
    org = await make_org("Index")
    lines = [("Maya", f"Sentence number {i} about the roadmap.") for i in range(6)]
    meeting_id = await make_indexed(org.schema_name, "Long one", lines, gap_ms=25_000)
    async with tenant_session(org.schema_name) as session:
        first = (
            await session.execute(
                select(SearchChunk.seq, SearchChunk.start_ms, SearchChunk.end_ms).order_by(
                    SearchChunk.seq
                )
            )
        ).all()
    assert first == [(0, 0, 50_500), (1, 75_000, 125_500)]  # about 60 s per chunk
    await run_index(org.schema_name, meeting_id)  # running again does not duplicate
    async with tenant_session(org.schema_name) as session:
        again = await session.scalar(select(func.count()).select_from(SearchChunk))
        meeting = await session.get(Meeting, meeting_id)
    assert again == 2 and meeting is not None and meeting.status == "ready"

    empty = await make_indexed(org.schema_name, "Silent", [])
    async with tenant_session(org.schema_name) as session:
        count = await session.scalar(
            select(func.count()).select_from(SearchChunk).where(SearchChunk.meeting_id == empty)
        )
        silent = await session.get(Meeting, empty)
    assert count == 0
    assert silent is not None and (silent.status, silent.stage) == ("ready", None)


async def test_index_failure_marks_incomplete_and_retry_runs_index(
    client: AsyncClient, google: FakeGoogle, monkeypatch: pytest.MonkeyPatch
) -> None:
    org, _, headers = await signed_in(client, google)
    meeting_id = await make_indexed(org.schema_name, "Broken", PLANNING)
    async with tenant_session(org.schema_name) as session:
        await session.execute(
            update(Meeting)
            .where(Meeting.id == meeting_id)
            .values(status="processing", stage="filing")
        )
        await queue.enqueue(session, "index", meeting_id)
    monkeypatch.setitem(
        registry._FACTORIES["embedding"],
        "down",
        lambda: FakeEmbedding(fail_times=9, retryable=False),
    )
    monkeypatch.setattr(get_settings(), "provider_embedding", "down")
    await Worker(max_attempts=1).run_once()
    detail = (await client.get(f"{MEETINGS}/{meeting_id}")).json()
    assert (detail["status"], detail["stage"], detail["error"]) == (
        "incomplete",
        "filing",
        INDEX_ERROR,
    )
    assert INDEX_ERROR == "Could not index the meeting for search."
    assert (await jobs(org.schema_name))[-1][1] == "failed"

    monkeypatch.setattr(get_settings(), "provider_embedding", "fake")
    retry = await client.post(f"{MEETINGS}/{meeting_id}/retry", headers=headers)
    assert retry.status_code == 200
    async with tenant_session(org.schema_name) as session:
        queued = await session.scalar(select(Job.kind).where(Job.state == "queued"))
    assert queued == "index"
    await run_worker()
    assert (await client.get(f"{MEETINGS}/{meeting_id}")).json()["status"] == "ready"


# ---- retrieval ----


async def test_search_finds_word_respects_scope_state_and_org() -> None:
    org_a, org_b = await make_org("Alpha"), await make_org("Beta")
    plan = await make_indexed(org_a.schema_name, "Planning", PLANNING, minutes=1)
    release = await make_indexed(org_a.schema_name, "Release", RELEASE, minutes=2)
    await make_indexed(org_b.schema_name, "Foreign", [("Eve", "The zebra secret lives here.")])
    await make_indexed(
        org_a.schema_name, "Draft", [("Eve", "zebra zebra zebra")], status="processing"
    )
    gone = await make_indexed(org_a.schema_name, "Gone", [("Eve", "zebra zebra zebra zebra")])
    async with tenant_session(org_a.schema_name) as session:
        await session.execute(
            update(Meeting).where(Meeting.id == gone).values(deleted_at=func.now())
        )

    async with tenant_session(org_a.schema_name) as session:
        found = await ask.search(session, "zebra campaign")
        assert found[0].meeting_id == plan and found[0].meeting_title == "Planning"
        assert found[0].start_ms == 0 and "Noah: Marketing wants the zebra" in found[0].text
        assert {c.meeting_id for c in found} == {plan, release}  # no draft, deleted or org B
        assert len(found) == 2 and len(await ask.search(session, "zebra", limit=1)) == 1

        scoped = await ask.search(session, "zebra campaign", scope_meeting_id=release)
        assert {c.meeting_id for c in scoped} == {release}  # vector part still fills the scope
        other = await ask.search(session, "regression", scope_meeting_id=plan)
        assert {c.meeting_id for c in other} == {plan}
        assert (await ask.search(session, "regression"))[0].meeting_id == release

        draft_only = await ask.search(session, "zebra", scope_meeting_id=gone)
        assert draft_only == []
    async with tenant_session(org_b.schema_name) as session:
        foreign = await ask.search(session, "zebra")
    assert [c.meeting_title for c in foreign] == ["Foreign"]
    async with tenant_session(org_a.schema_name) as session:
        usage = await session.scalar(
            select(func.count())
            .select_from(UsageEvent)
            .where(UsageEvent.function == "embedding", UsageEvent.meeting_id.is_(None))
        )
    assert usage and usage >= 5  # each question was embedded and metered


# ---- conversations ----


async def test_conversation_crud_scope_and_user_isolation(
    client: AsyncClient, google: FakeGoogle
) -> None:
    org, _, headers = await signed_in(client, google)
    meeting = await make_indexed(org.schema_name, "Planning", PLANNING)
    assert (await client.get(CONVERSATIONS)).json() == {"items": []}

    created = await client.post(CONVERSATIONS, json={}, headers=headers)
    assert created.status_code == 201
    body = created.json()
    assert set(body) == {"id", "title", "scope_meeting_id", "updated_at"}
    assert body["title"] is None and body["scope_meeting_id"] is None
    scoped = await client.post(
        CONVERSATIONS, json={"scope_meeting_id": str(meeting)}, headers=headers
    )
    assert scoped.status_code == 201 and scoped.json()["scope_meeting_id"] == str(meeting)

    listed = (await client.get(CONVERSATIONS)).json()["items"]
    assert [i["id"] for i in listed] == [scoped.json()["id"], body["id"]]  # newest first
    detail = (await client.get(f"{CONVERSATIONS}/{body['id']}")).json()
    assert detail == {"id": body["id"], "title": None, "scope_meeting_id": None, "messages": []}

    bad = await client.post(
        CONVERSATIONS, json={"scope_meeting_id": str(uuid.uuid4())}, headers=headers
    )
    assert bad.status_code == 404 and bad.json()["error"]["code"] == "meeting_not_found"
    invalid = await client.post(CONVERSATIONS, json={"scope_meeting_id": "nope"}, headers=headers)
    assert invalid.status_code == 400 and invalid.json()["error"]["code"] == "validation_error"
    other_org = await make_org("Other")
    foreign = await make_indexed(other_org.schema_name, "Foreign", PLANNING)
    cross = await client.post(
        CONVERSATIONS, json={"scope_meeting_id": str(foreign)}, headers=headers
    )
    assert cross.status_code == 404

    # A second user of the same organization sees none of it.
    first_cookie = client.cookies["recapz_session"]
    await add_member(org, "second@example.com")
    await sign_in(client, google, "second@example.com")
    second_headers = {"X-CSRF-Token": (await client.get("/api/v1/me")).json()["csrf_token"]}
    assert (await client.get(CONVERSATIONS)).json() == {"items": []}
    for response in (
        await client.get(f"{CONVERSATIONS}/{body['id']}"),
        await client.delete(f"{CONVERSATIONS}/{body['id']}", headers=second_headers),
        await ask_question(client, second_headers, body["id"], "hello"),
    ):
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "conversation_not_found"
    use_session(client, first_cookie)
    assert len((await client.get(CONVERSATIONS)).json()["items"]) == 2

    # delete
    assert (await client.delete(f"{CONVERSATIONS}/{body['id']}")).status_code == 403
    assert (
        await client.delete(f"{CONVERSATIONS}/{body['id']}", headers=headers)
    ).status_code == 204
    gone = await client.get(f"{CONVERSATIONS}/{body['id']}")
    assert gone.status_code == 404 and gone.json()["error"]["code"] == "conversation_not_found"
    assert (
        await client.delete(f"{CONVERSATIONS}/{body['id']}", headers=headers)
    ).status_code == 404
    assert len((await client.get(CONVERSATIONS)).json()["items"]) == 1


async def test_ask_endpoints_need_sign_in_and_csrf(client: AsyncClient, google: FakeGoogle) -> None:
    cid = str(uuid.uuid4())
    assert (await client.get(CONVERSATIONS)).status_code == 401
    assert (await client.get(f"{CONVERSATIONS}/{cid}")).status_code == 401
    assert (await client.get(HOME)).status_code == 401
    assert (await client.post(CONVERSATIONS, json={})).status_code == 401
    org, _, headers = await signed_in(client, google)
    conversation = await new_conversation(client, headers)
    for response in (
        await client.post(CONVERSATIONS, json={}),
        await client.post(f"{CONVERSATIONS}/{conversation}/messages", json={"text": "hi"}),
        await client.delete(f"{CONVERSATIONS}/{conversation}"),
    ):
        assert response.status_code == 403 and response.json()["error"]["code"] == "csrf_failed"
    async with tenant_session(org.schema_name) as session:
        assert await session.scalar(select(func.count()).select_from(Message)) == 0


async def test_message_text_is_validated(client: AsyncClient, google: FakeGoogle) -> None:
    _, _, headers = await signed_in(client, google)
    conversation = await new_conversation(client, headers)
    for body in ({"text": ""}, {"text": "   "}, {"text": "x" * 2001}, {}):
        response = await client.post(
            f"{CONVERSATIONS}/{conversation}/messages", json=body, headers=headers
        )
        assert (
            response.status_code == 400 and response.json()["error"]["code"] == "validation_error"
        )
    ok = await ask_question(client, headers, conversation, "x" * 2000)
    assert ok.status_code == 200
    assert (await client.get(f"{CONVERSATIONS}/{conversation}")).json()["messages"][0][
        "text"
    ] == "x" * 2000


# ---- answers ----


async def test_answer_streams_tokens_then_citations_then_done(
    client: AsyncClient, google: FakeGoogle, monkeypatch: pytest.MonkeyPatch
) -> None:
    org, _, headers = await signed_in(client, google)
    plan = await make_indexed(org.schema_name, "Planning", PLANNING, minutes=1)
    release = await make_indexed(org.schema_name, "Release", RELEASE, minutes=2)
    llm = use_llm(monkeypatch, FakeLlm())
    conversation = await new_conversation(client, headers)
    question = "What did Marketing say about the zebra campaign?"
    response = await ask_question(client, headers, conversation, question)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    events = parse_sse(response)
    names = [n for n, _ in events]
    assert set(names[:-2]) == {"token"} and names[-2:] == ["citations", "done"]
    streamed = "".join(str(d["text"]) for n, d in events if n == "token")
    assert streamed.startswith("According to the meeting, ") and "[c1]" in streamed
    assert len([n for n in names if n == "token"]) > 3  # more than one piece
    citations = events[-2][1]["items"]
    assert citations[0] == {"meeting_id": str(plan), "meeting_title": "Planning", "at_ms": 0}
    assert {c["meeting_id"] for c in citations} <= {str(plan), str(release)}
    assert llm.calls == 1

    detail = (await client.get(f"{CONVERSATIONS}/{conversation}")).json()
    assert detail["title"] == question[:60]
    user, assistant = detail["messages"]
    assert (user["role"], user["text"], user["status"], user["citations"]) == (
        "user",
        question,
        "done",
        [],
    )
    assert set(user) == {"id", "role", "text", "status", "created_at", "citations"}
    assert assistant["role"] == "assistant" and assistant["status"] == "done"
    assert assistant["id"] == events[-1][1]["message_id"]
    assert "[c" not in assistant["text"]  # labels are stripped from the stored text
    assert assistant["text"] == ask.strip_labels(streamed)
    assert assistant["citations"] == citations

    # The conversation moves up the list; a second question keeps the first title.
    other = await new_conversation(client, headers)
    assert [i["id"] for i in (await client.get(CONVERSATIONS)).json()["items"]][0] == other
    await ask_question(client, headers, conversation, "And the regression tests?")
    listing = (await client.get(CONVERSATIONS)).json()["items"]
    assert listing[0]["id"] == conversation and listing[0]["title"] == question[:60]
    assert len((await client.get(f"{CONVERSATIONS}/{conversation}")).json()["messages"]) == 4

    # usage of the answer is metered without a meeting
    async with tenant_session(org.schema_name) as session:
        rows = (
            await session.execute(
                select(UsageEvent.unit_kind, UsageEvent.units).where(
                    UsageEvent.function == "llm", UsageEvent.meeting_id.is_(None)
                )
            )
        ).all()
    assert {k for k, _ in rows} == {"input_tokens", "output_tokens"} and len(rows) == 4
    assert all(units > 0 for _, units in rows)


async def test_scoped_conversation_cites_only_its_meeting(
    client: AsyncClient, google: FakeGoogle
) -> None:
    org, _, headers = await signed_in(client, google)
    await make_indexed(org.schema_name, "Planning", PLANNING)
    release = await make_indexed(org.schema_name, "Release", RELEASE, minutes=5)
    conversation = await new_conversation(client, headers, str(release))
    events = parse_sse(await ask_question(client, headers, conversation, "zebra campaign"))
    items = events[-2][1]["items"]
    assert items and {i["meeting_id"] for i in items} == {str(release)}


async def test_no_match_answers_without_calling_the_llm(
    client: AsyncClient, google: FakeGoogle, monkeypatch: pytest.MonkeyPatch
) -> None:
    org, _, headers = await signed_in(client, google)
    llm = use_llm(monkeypatch, FakeLlm())
    conversation = await new_conversation(client, headers)
    events = parse_sse(await ask_question(client, headers, conversation, "anything at all"))
    assert [n for n, _ in events] == ["token", "citations", "done"]
    assert events[0][1] == {"text": NOT_FOUND}
    assert events[1][1] == {"items": []}
    assert llm.calls == 0

    meeting = await make_indexed(org.schema_name, "Silent", [])
    scoped = await new_conversation(client, headers, str(meeting))
    events = parse_sse(await ask_question(client, headers, scoped, "anything"))
    assert str(events[0][1]["text"]).startswith("I could not find that in this meeting.")
    assert llm.calls == 0
    detail = (await client.get(f"{CONVERSATIONS}/{scoped}")).json()
    assert detail["messages"][1]["text"] == events[0][1]["text"]
    assert detail["messages"][1]["citations"] == [] and detail["messages"][1]["status"] == "done"


async def test_provider_error_emits_error_and_stores_failed_message(
    client: AsyncClient, google: FakeGoogle, monkeypatch: pytest.MonkeyPatch
) -> None:
    org, _, headers = await signed_in(client, google)
    await make_indexed(org.schema_name, "Planning", PLANNING)
    use_llm(monkeypatch, FakeLlm(fail_times=9, retryable=False))
    conversation = await new_conversation(client, headers)
    response = await ask_question(client, headers, conversation, "zebra campaign")
    assert response.status_code == 200
    assert parse_sse(response) == [
        (
            "error",
            {
                "code": "provider_unavailable",
                "message": "The assistant is unavailable right now. Try again.",
            },
        )
    ]
    detail = (await client.get(f"{CONVERSATIONS}/{conversation}")).json()
    assert [(m["role"], m["status"]) for m in detail["messages"]] == [
        ("user", "done"),
        ("assistant", "failed"),
    ]
    assert detail["messages"][1]["text"] == "" and detail["messages"][1]["citations"] == []
    async with tenant_session(org.schema_name) as session:
        assert await session.scalar(select(func.count()).select_from(Citation)) == 0

    # The next question works once the provider is back.
    use_llm(monkeypatch, FakeLlm())
    events = parse_sse(await ask_question(client, headers, conversation, "zebra campaign"))
    assert events[-1][0] == "done"


async def test_embedding_error_also_ends_with_error_event(
    client: AsyncClient, google: FakeGoogle, monkeypatch: pytest.MonkeyPatch
) -> None:
    org, _, headers = await signed_in(client, google)
    await make_indexed(org.schema_name, "Planning", PLANNING)
    monkeypatch.setitem(
        registry._FACTORIES["embedding"],
        "down",
        lambda: FakeEmbedding(fail_times=9, retryable=False),
    )
    monkeypatch.setattr(get_settings(), "provider_embedding", "down")
    conversation = await new_conversation(client, headers)
    events = parse_sse(await ask_question(client, headers, conversation, "zebra"))
    assert [n for n, _ in events] == ["error"]
    detail = (await client.get(f"{CONVERSATIONS}/{conversation}")).json()
    assert detail["messages"][1]["status"] == "failed"


async def test_deleting_a_meeting_removes_its_chunks_and_citations(
    client: AsyncClient, google: FakeGoogle
) -> None:
    org, _, headers = await signed_in(client, google)
    plan = await make_indexed(org.schema_name, "Planning", PLANNING)
    conversation = await new_conversation(client, headers)
    events = parse_sse(await ask_question(client, headers, conversation, "zebra campaign"))
    assert events[-2][1]["items"]
    scoped = await new_conversation(client, headers, str(plan))
    async with tenant_session(org.schema_name) as session:
        assert await session.scalar(select(func.count()).select_from(SearchChunk)) == 1
        assert await session.scalar(select(func.count()).select_from(Citation)) >= 1

    assert (await client.delete(f"{MEETINGS}/{plan}", headers=headers)).status_code == 204
    async with tenant_session(org.schema_name) as session:
        assert await session.scalar(select(func.count()).select_from(SearchChunk)) == 0
        assert await session.scalar(select(func.count()).select_from(Citation)) == 0
    detail = (await client.get(f"{CONVERSATIONS}/{conversation}")).json()
    assert [m["role"] for m in detail["messages"]] == ["user", "assistant"]
    assert detail["messages"][1]["citations"] == []
    kept = (await client.get(f"{CONVERSATIONS}/{scoped}")).json()
    assert kept["scope_meeting_id"] is None  # the chat stays, now without a scope


# ---- home ----


async def add_follow_ups(
    schema: str, meeting_id: uuid.UUID, owner: uuid.UUID | None, count: int, state: str = "open"
) -> None:
    async with tenant_session(schema) as session:
        base = datetime.now(UTC)
        for i in range(count):
            session.add(
                FollowUp(
                    meeting_id=meeting_id,
                    text=f"Task {state} {i}",
                    owner_user_id=owner,
                    at_ms=i * 1000,
                    state=state,
                    created_at=base + timedelta(microseconds=i),
                )
            )


async def test_home_shapes_and_limits(client: AsyncClient, google: FakeGoogle) -> None:
    org, user_id, headers = await signed_in(client, google)
    empty = (await client.get(HOME)).json()
    assert empty == {"needs_you": [], "recent_meetings": [], "has_any_meeting": False}

    busy = await make_indexed(org.schema_name, "Still processing", PLANNING, status="processing")
    home = (await client.get(HOME)).json()
    assert home["has_any_meeting"] is True and home["recent_meetings"] == []

    ids = [
        await make_indexed(org.schema_name, f"Meeting {n}", PLANNING, minutes=n)
        for n in range(1, 5)
    ]
    await add_follow_ups(org.schema_name, ids[0], user_id, 3)
    await add_follow_ups(org.schema_name, ids[1], user_id, 3)
    await add_follow_ups(org.schema_name, ids[1], user_id, 2, state="done")
    await add_follow_ups(org.schema_name, ids[2], None, 2)  # nobody owns these
    await add_follow_ups(org.schema_name, busy, user_id, 1)  # meeting is not ready
    stranger = await add_member(org, "other@example.com")
    await add_follow_ups(org.schema_name, ids[3], stranger, 2)

    home = (await client.get(HOME)).json()
    assert set(home) == {"needs_you", "recent_meetings", "has_any_meeting"}
    assert len(home["needs_you"]) == 4
    assert all(
        i["state"] == "open" and i["owner_user_id"] == str(user_id) for i in home["needs_you"]
    )
    assert set(home["needs_you"][0]) == {
        "id",
        "text",
        "owner_name",
        "owner_user_id",
        "at_ms",
        "state",
        "meeting_id",
        "meeting_title",
    }
    assert home["needs_you"][0]["meeting_title"] == "Meeting 2"  # newest meeting first
    assert [m["title"] for m in home["recent_meetings"]] == ["Meeting 4", "Meeting 3", "Meeting 2"]
    listed = (await client.get(MEETINGS, params={"status": "ready"})).json()["items"]
    assert home["recent_meetings"] == listed[:3]  # same shape as the meetings list
    assert set(home["recent_meetings"][0]) >= {"id", "title", "status", "participants", "folder"}
    assert len(home["recent_meetings"][0]["participants"]) == 2

    # Deleted meetings do not count; another org's data never shows.
    for mid in (*ids, busy):
        assert (await client.delete(f"{MEETINGS}/{mid}", headers=headers)).status_code == 204
    other = await make_org("Other")
    await make_indexed(other.schema_name, "Not mine", PLANNING)
    assert (await client.get(HOME)).json() == {
        "needs_you": [],
        "recent_meetings": [],
        "has_any_meeting": False,
    }
