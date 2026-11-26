import asyncio

from sqlalchemy import func, select

from app.db.cli import main
from app.db.models.public import Invite, Organization
from app.db.session import get_engine, get_sessionmaker, reset_engine_cache
from tests.integration.conftest import FakeGoogle, sign_in


def run_seed() -> None:
    main(
        ["seed", "--org", "Northwind", "--owner-email", "Boss@Example.com", "--owner-name", "Boss"]
    )


async def seed_cli() -> None:
    # The CLI runs its own event loop, so it needs a fresh engine each time.
    await get_engine().dispose()
    reset_engine_cache()
    await asyncio.to_thread(run_seed)
    reset_engine_cache()


async def test_seed_is_idempotent() -> None:
    await seed_cli()
    await seed_cli()
    async with get_sessionmaker()() as db:
        orgs = (await db.scalars(select(Organization))).all()
        invites = (await db.scalars(select(Invite))).all()
        assert len(orgs) == 1 and orgs[0].name == "Northwind"
        assert len(invites) == 1
        assert invites[0].role == "owner" and invites[0].email == "boss@example.com"
        assert invites[0].accepted_at is None
        total = await db.scalar(select(func.count()).select_from(Organization))
        assert total == 1


async def test_seeded_owner_can_sign_in(client, google: FakeGoogle) -> None:  # type: ignore[no-untyped-def]
    await seed_cli()
    response = await sign_in(client, google, "boss@example.com")
    assert response.headers["location"].endswith("/home")
    me = (await client.get("/api/v1/me")).json()
    assert me["role"] == "owner" and me["organization"]["name"] == "Northwind"
    await seed_cli()  # now a member: no new invite
    async with get_sessionmaker()() as db:
        assert len((await db.scalars(select(Invite))).all()) == 1
