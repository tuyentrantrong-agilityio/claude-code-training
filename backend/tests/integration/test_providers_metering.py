import uuid
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import select

from app.db.models.org import Meeting, UsageEvent
from app.db.session import tenant_session
from app.providers.base import ProviderError
from app.providers.fakes import FakeBatchStt, FakeEmbedding, FakeLlm, FakeTts
from app.providers.metering import MeteredBatchStt, MeteredEmbedding, MeteredLlm, MeteredTts
from app.providers.types import ChatMessage

FIXTURES = Path(__file__).parent.parent / "fixtures"


async def _no_sleep(seconds: float) -> None:
    return None


async def _meeting(schema: str) -> uuid.UUID:
    async with tenant_session(schema) as session:
        meeting = Meeting(
            title="m", source="upload", platform="file", language="en", status="processing"
        )
        session.add(meeting)
        await session.flush()
        return meeting.id


async def _events(schema: str, meeting_id: uuid.UUID) -> list[UsageEvent]:
    async with tenant_session(schema) as session:
        rows = await session.scalars(select(UsageEvent).where(UsageEvent.meeting_id == meeting_id))
        return list(rows)


async def test_metered_calls_write_usage_events(two_orgs: tuple[str, str]) -> None:
    schema, other = two_orgs
    meeting_id = await _meeting(schema)
    async with tenant_session(schema) as session:
        stt = MeteredBatchStt(FakeBatchStt(), session, meeting_id, sleep=_no_sleep)
        await stt.transcribe(FIXTURES / "sample.wav", "en")
        llm = MeteredLlm(FakeLlm(), session, meeting_id, sleep=_no_sleep)
        await llm.complete([ChatMessage("user", "one two three")], max_tokens=10)
        emb = MeteredEmbedding(FakeEmbedding(), session, meeting_id, sleep=_no_sleep)
        await emb.embed(["a b", "c"])
        tts = MeteredTts(FakeTts(), session, meeting_id, sleep=_no_sleep)
        await tts.synthesize("hello", "en")

    rows = {(e.function, e.unit_kind): e for e in await _events(schema, meeting_id)}
    assert len(rows) == 5
    stt_row = rows[("stt", "audio_seconds")]
    assert stt_row.units == Decimal("12")
    assert stt_row.provider == "fake"
    assert rows[("llm", "input_tokens")].units == Decimal("3")
    assert rows[("llm", "output_tokens")].units == Decimal(len(FakeLlm.canned.split()))
    assert rows[("embedding", "input_tokens")].units == Decimal("3")
    assert rows[("tts", "characters")].units == Decimal("5")

    async with tenant_session(other) as session:
        assert list(await session.scalars(select(UsageEvent))) == []


async def test_retry_then_success_records_once(two_orgs: tuple[str, str]) -> None:
    schema, _ = two_orgs
    meeting_id = await _meeting(schema)
    async with tenant_session(schema) as session:
        emb = MeteredEmbedding(FakeEmbedding(fail_times=1), session, meeting_id, sleep=_no_sleep)
        await emb.embed(["x"])
    assert len(await _events(schema, meeting_id)) == 1


async def test_failed_call_writes_nothing(two_orgs: tuple[str, str]) -> None:
    schema, _ = two_orgs
    meeting_id = await _meeting(schema)
    with pytest.raises(ProviderError):
        async with tenant_session(schema) as session:
            llm = MeteredLlm(
                FakeLlm(fail_times=10), session, meeting_id, max_retries=1, sleep=_no_sleep
            )
            await llm.complete([ChatMessage("user", "x")], max_tokens=10)
    assert await _events(schema, meeting_id) == []
