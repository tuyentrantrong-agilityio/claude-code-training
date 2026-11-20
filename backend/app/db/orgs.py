import asyncio
import secrets

from sqlalchemy import select, text

from app.db.migrate import upgrade_org
from app.db.models.public import Organization
from app.db.session import get_sessionmaker, validate_schema_name


def new_schema_name() -> str:
    return f"org_{secrets.token_hex(6)}"


async def create_organization(name: str) -> Organization:
    schema_name = validate_schema_name(new_schema_name())
    async with get_sessionmaker()() as session, session.begin():
        org = Organization(name=name, schema_name=schema_name)
        session.add(org)
        await session.flush()
        await session.execute(text(f'CREATE SCHEMA "{schema_name}"'))
    await asyncio.to_thread(upgrade_org, schema_name)
    return org


async def migrate_all_orgs() -> list[str]:
    async with get_sessionmaker()() as session:
        rows = await session.scalars(select(Organization.schema_name).order_by(Organization.name))
        schemas = list(rows)
    for schema_name in schemas:
        await asyncio.to_thread(upgrade_org, validate_schema_name(schema_name))
    return schemas
