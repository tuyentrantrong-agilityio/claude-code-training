import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError

from app.db.models.org import Meeting, TranscriptSegment
from app.db.session import tenant_session


def _meeting() -> Meeting:
    return Meeting(
        title="Weekly sync",
        source="upload",
        platform="file",
        language="en",
        status="processing",
    )


async def test_orgs_are_isolated(two_orgs: tuple[str, str]) -> None:
    schema_a, schema_b = two_orgs
    async with tenant_session(schema_a) as session:
        session.add(_meeting())

    async with tenant_session(schema_a) as session:
        count_a = await session.scalar(select(func.count()).select_from(Meeting))
    async with tenant_session(schema_b) as session:
        count_b = await session.scalar(select(func.count()).select_from(Meeting))

    assert count_a == 1
    assert count_b == 0


async def test_org_schema_has_own_version_table(two_orgs: tuple[str, str]) -> None:
    async with tenant_session(two_orgs[0]) as session:
        version = await session.scalar(
            text(f'SELECT version_num FROM "{two_orgs[0]}".alembic_version')
        )
    assert version == "0002_search_and_ask"  # head after the Ask migration


async def test_segment_seq_is_unique(two_orgs: tuple[str, str]) -> None:
    with pytest.raises(IntegrityError):
        async with tenant_session(two_orgs[0]) as session:
            meeting = _meeting()
            session.add(meeting)
            await session.flush()
            for _ in range(2):
                session.add(
                    TranscriptSegment(
                        meeting_id=meeting.id, seq=1, start_ms=0, end_ms=10, text="hello"
                    )
                )
            await session.flush()


async def test_deleting_meeting_cascades(two_orgs: tuple[str, str]) -> None:
    async with tenant_session(two_orgs[0]) as session:
        meeting = _meeting()
        session.add(meeting)
        await session.flush()
        session.add(TranscriptSegment(meeting_id=meeting.id, seq=1, start_ms=0, end_ms=5, text="a"))
        await session.flush()
        meeting_id = meeting.id

    async with tenant_session(two_orgs[0]) as session:
        await session.execute(text("DELETE FROM meetings WHERE id = :id"), {"id": meeting_id})
        left = await session.scalar(select(func.count()).select_from(TranscriptSegment))

    assert left == 0
