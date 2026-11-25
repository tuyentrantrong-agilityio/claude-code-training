import asyncio
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, text

from app.core.settings import get_settings
from app.db.migrate import upgrade_org
from app.db.models.public import Invite, Membership, Organization, User
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


@dataclass(frozen=True)
class SeedResult:
    organization: Organization
    created_org: bool
    invite_status: str  # created, refreshed, exists, already_member


async def seed_organization(name: str, owner_email: str, owner_name: str) -> SeedResult:
    """Create the org if missing and leave a pending OWNER invite for the first owner."""
    email = owner_email.strip().lower()
    async with get_sessionmaker()() as session:
        org = await session.scalar(
            select(Organization).where(Organization.name == name).order_by(Organization.created_at)
        )
    created_org = org is None
    if org is None:
        org = await create_organization(name)
    now = datetime.now(UTC)
    expires = now + timedelta(days=get_settings().invite_ttl_days)
    async with get_sessionmaker()() as session, session.begin():
        user = await session.scalar(select(User).where(User.email == email))
        if user is None:
            user = User(email=email, name=owner_name)
            session.add(user)
            await session.flush()
        member = await session.scalar(
            select(Membership).where(
                Membership.organization_id == org.id, Membership.user_id == user.id
            )
        )
        if member is not None:
            return SeedResult(org, created_org, "already_member")
        invite = await session.scalar(
            select(Invite).where(
                Invite.organization_id == org.id,
                Invite.email == email,
                Invite.accepted_at.is_(None),
                Invite.revoked_at.is_(None),
            )
        )
        if invite is None:
            session.add(
                Invite(organization_id=org.id, email=email, role="owner", expires_at=expires)
            )
            return SeedResult(org, created_org, "created")
        if invite.expires_at <= now or invite.role != "owner":
            invite.expires_at = expires
            invite.role = "owner"
            return SeedResult(org, created_org, "refreshed")
        return SeedResult(org, created_org, "exists")
