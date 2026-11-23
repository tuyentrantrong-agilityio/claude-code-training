import asyncio
import os
import socket
from collections.abc import AsyncIterator, Iterator

import asyncpg
import pytest
from sqlalchemy.engine import make_url

from app.core.settings import get_settings
from app.db.migrate import upgrade_public
from app.db.orgs import create_organization
from app.db.session import get_engine, reset_engine_cache

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
