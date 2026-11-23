import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import lru_cache

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.settings import get_settings

SCHEMA_RE = re.compile(r"^org_[0-9a-f]{12}$")


def validate_schema_name(schema_name: str) -> str:
    if not SCHEMA_RE.fullmatch(schema_name):
        raise ValueError(f"invalid schema name: {schema_name!r}")
    return schema_name


@lru_cache
def get_engine() -> AsyncEngine:
    return create_async_engine(get_settings().database_url, pool_pre_ping=True)


@lru_cache
def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(get_engine(), expire_on_commit=False)


def reset_engine_cache() -> None:
    """Forget the cached engine (tests; the caller disposes the old one)."""
    get_sessionmaker.cache_clear()
    get_engine.cache_clear()


async def ping() -> None:
    async with get_engine().connect() as conn:
        await conn.execute(text("SELECT 1"))


@asynccontextmanager
async def tenant_session(schema_name: str) -> AsyncIterator[AsyncSession]:
    """Session in one transaction with search_path set to the org schema."""
    validate_schema_name(schema_name)
    async with get_sessionmaker()() as session, session.begin():
        await session.execute(text(f'SET LOCAL search_path TO "{schema_name}", public'))
        yield session


async def get_public_session() -> AsyncIterator[AsyncSession]:
    async with get_sessionmaker()() as session:
        yield session
