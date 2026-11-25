import asyncio
import os
import socket
import uuid
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime, timedelta

import asyncpg
import pytest
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy.engine import make_url

from app.api.v1.auth import STATE_COOKIE
from app.core.security import new_state
from app.core.settings import get_settings
from app.db.migrate import upgrade_public
from app.db.models.public import Invite, Membership, Organization, User
from app.db.orgs import create_organization
from app.db.session import get_engine, get_sessionmaker, reset_engine_cache
from app.main import app
from app.providers.google import GoogleAuthError, GoogleIdentity, get_google_client

TEST_DB = "recapz_test"


def _base_url() -> str:
    return os.environ.get("DATABASE_URL") or get_settings().database_url


def _reachable() -> bool:
    url = make_url(_base_url())
    try:
        with socket.create_connection((url.host or "localhost", url.port or 5432), timeout=1):
            return True
    except OSError:
        return False


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    here = os.path.dirname(__file__)
    skip = None
    for item in items:
        if not str(item.fspath).startswith(here):
            continue
        item.add_marker(pytest.mark.integration)
        if skip is None and not _reachable():
            skip = pytest.mark.skip(reason="database is unreachable")
        if skip is not None:
            item.add_marker(skip)


def _dsn(db: str) -> str:
    url = make_url(_base_url()).set(drivername="postgresql", database=db)
    return url.render_as_string(hide_password=False)


async def _prepare_database() -> None:
    admin = await asyncpg.connect(_dsn("postgres"))
    try:
        exists = await admin.fetchval("SELECT 1 FROM pg_database WHERE datname = $1", TEST_DB)
        if not exists:
            await admin.execute(f'CREATE DATABASE "{TEST_DB}"')
    finally:
        await admin.close()
    conn = await asyncpg.connect(_dsn(TEST_DB))
    try:
        schemas = await conn.fetch("SELECT nspname FROM pg_namespace WHERE nspname LIKE 'org\\_%'")
        for row in schemas:
            await conn.execute(f'DROP SCHEMA "{row["nspname"]}" CASCADE')
        await conn.execute("DROP SCHEMA public CASCADE")
        await conn.execute("CREATE SCHEMA public")
    finally:
        await conn.close()


@pytest.fixture(scope="session", autouse=True)
def test_database() -> Iterator[None]:
    if not _reachable():
        yield
        return
    previous = os.environ.get("DATABASE_URL")
    test_url = make_url(_base_url()).set(database=TEST_DB).render_as_string(hide_password=False)
    asyncio.run(_prepare_database())
    os.environ["DATABASE_URL"] = test_url
    get_settings.cache_clear()
    reset_engine_cache()
    upgrade_public()
    yield
    if previous is None:
        os.environ.pop("DATABASE_URL", None)
    else:
        os.environ["DATABASE_URL"] = previous
    get_settings.cache_clear()
    reset_engine_cache()


@pytest.fixture(autouse=True)
async def clean_identity_tables(test_database: None) -> None:
    if not _reachable():
        return
    conn = await asyncpg.connect(_dsn(TEST_DB))
    try:
        await conn.execute(
            "TRUNCATE sessions, invites, memberships, users, organizations RESTART IDENTITY CASCADE"
        )
    finally:
        await conn.close()


@pytest.fixture(autouse=True)
async def fresh_engine() -> AsyncIterator[None]:
    # Engines are bound to the event loop of the test that created them.
    yield
    await get_engine().dispose()
    reset_engine_cache()


@pytest.fixture
async def two_orgs() -> tuple[str, str]:
    org_a = await create_organization("Org A")
    org_b = await create_organization("Org B")
    return org_a.schema_name, org_b.schema_name


# ---- auth helpers ----


class FakeGoogle:
    """Stands in for GoogleClient; the "code" is looked up in identities."""

    def __init__(self) -> None:
        self.identities: dict[str, GoogleIdentity] = {}

    def allow(self, email: str, name: str = "Test User", sub: str | None = None) -> str:
        code = f"code-{email}"
        self.identities[code] = GoogleIdentity(sub=sub or f"sub-{email}", email=email, name=name)
        return code

    async def exchange_code(self, code: str) -> str:
        if code not in self.identities:
            raise GoogleAuthError("bad code")
        return code

    async def verify_id_token(self, id_token: str) -> GoogleIdentity:
        return self.identities[id_token]


@pytest.fixture
def google() -> FakeGoogle:
    return FakeGoogle()


@pytest.fixture
async def client(google: FakeGoogle) -> AsyncIterator[AsyncClient]:
    app.dependency_overrides[get_google_client] = lambda: google
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


async def make_org(name: str = "Acme") -> Organization:
    return await create_organization(name)


async def add_user(email: str, name: str = "Someone") -> uuid.UUID:
    async with get_sessionmaker()() as db, db.begin():
        user = User(email=email, name=name)
        db.add(user)
        await db.flush()
        return user.id


async def add_member(org: Organization, email: str, role: str = "member") -> uuid.UUID:
    user_id = await add_user(email)
    async with get_sessionmaker()() as db, db.begin():
        db.add(Membership(organization_id=org.id, user_id=user_id, role=role))
    return user_id


async def add_invite(
    org: Organization, email: str, role: str = "member", expires_in_days: float = 7
) -> uuid.UUID:
    async with get_sessionmaker()() as db, db.begin():
        invite = Invite(
            organization_id=org.id,
            email=email,
            role=role,
            expires_at=datetime.now(UTC) + timedelta(days=expires_in_days),
        )
        db.add(invite)
        await db.flush()
        return invite.id


async def sign_in(client: AsyncClient, google: FakeGoogle, email: str) -> Response:
    """Run the callback with a valid state cookie for an identity Google would return."""
    code = google.allow(email)
    state, cookie = new_state(get_settings().secret_key)
    return await client.get(
        "/api/v1/auth/google/callback",
        params={"code": code, "state": state},
        headers={"Cookie": f"{STATE_COOKIE}={cookie}"},
    )


def use_session(client: AsyncClient, token: str) -> None:
    client.cookies.clear()
    client.cookies.set("recapz_session", token)


async def csrf_headers(client: AsyncClient) -> dict[str, str]:
    me = (await client.get("/api/v1/me")).json()
    return {"X-CSRF-Token": me["csrf_token"]}
