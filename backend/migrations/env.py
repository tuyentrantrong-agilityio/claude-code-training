import asyncio
from typing import Any

from alembic import context
from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from app.core.settings import get_settings
from app.db.session import validate_schema_name

config = context.config


def _option(name: str) -> Any:
    value = config.attributes.get(name)
    if value is None:
        value = context.get_x_argument(as_dictionary=True).get(name)
    return value


target = _option("target") or "public"
if target not in ("public", "org"):
    raise ValueError(f"unknown target: {target!r}")
schema: str | None = None
if target == "org":
    schema = validate_schema_name(str(_option("schema") or ""))
    # CLI runs use alembic.ini (public locations); switch to the org branch.
    context.script.version_locations = [str(context.script.dir) + "/org"]
elif not config.attributes.get("target"):
    context.script.version_locations = [str(context.script.dir) + "/public"]


def _run(connection: Connection) -> None:
    version_schema = "public" if schema is None else schema
    context.configure(
        connection=connection,
        target_metadata=None,
        version_table="alembic_version",
        version_table_schema=version_schema,
    )
    with context.begin_transaction():
        context.run_migrations()


async def _run_async() -> None:
    url = _option("database_url") or get_settings().database_url
    engine = create_async_engine(url, poolclass=NullPool)
    try:
        async with engine.begin() as connection:
            if schema is not None:
                await connection.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))
                await connection.execute(text(f'SET LOCAL search_path TO "{schema}", public'))
            await connection.run_sync(_run)
    finally:
        await engine.dispose()


if context.is_offline_mode():
    raise RuntimeError("offline mode is not supported")
asyncio.run(_run_async())
