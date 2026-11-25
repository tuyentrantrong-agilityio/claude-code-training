import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import Select, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_token, new_session_token
from app.db.models.public import Invite, Membership, User
from app.db.models.public import Session as SessionRow
from app.providers.google import GoogleIdentity


def pending_invites(email: str) -> Select[Invite]:
    return select(Invite).where(
        Invite.email == email,
        Invite.accepted_at.is_(None),
        Invite.revoked_at.is_(None),
        Invite.expires_at > func.now(),
    )


async def first_membership(db: AsyncSession, user_id: uuid.UUID) -> Membership | None:
    stmt = (
        select(Membership)
        .where(Membership.user_id == user_id)
        .order_by(Membership.created_at, Membership.organization_id)
        .limit(1)
    )
    return await db.scalar(stmt)


async def create_session(
    db: AsyncSession,
    user_id: uuid.UUID,
    organization_id: uuid.UUID,
    user_agent: str | None,
    ttl_days: int,
) -> str:
    """Store a new session and return the raw cookie token."""
    token = new_session_token()
    db.add(
        SessionRow(
            id=hash_token(token),
            user_id=user_id,
            organization_id=organization_id,
            user_agent=user_agent,
            expires_at=datetime.now(UTC) + timedelta(days=ttl_days),
        )
    )
    return token


async def sign_in(
    db: AsyncSession, identity: GoogleIdentity, user_agent: str | None, ttl_days: int
) -> str | None:
    """Return a session token, or None when the email is not invited. Caller commits."""
    now = datetime.now(UTC)
    user = await db.scalar(select(User).where(User.email == identity.email))
    if user is not None and user.google_sub and user.google_sub != identity.sub:
        return None
    membership = await first_membership(db, user.id) if user is not None else None
    organization_id: uuid.UUID
    if membership is not None:
        organization_id = membership.organization_id
    else:
        invite = await db.scalar(
            pending_invites(identity.email).order_by(Invite.created_at).limit(1)
        )
        if invite is None:
            return None
        if user is None:
            user = User(email=identity.email, name=identity.name or identity.email.split("@")[0])
            db.add(user)
            await db.flush()
        db.add(
            Membership(organization_id=invite.organization_id, user_id=user.id, role=invite.role)
        )
        invite.accepted_at = now
        organization_id = invite.organization_id
    assert user is not None
    user.google_sub = identity.sub
    if identity.name:
        user.name = identity.name
    user.last_sign_in_at = now
    await db.flush()
    return await create_session(db, user.id, organization_id, user_agent, ttl_days)


async def revoke_session(db: AsyncSession, session_id: str) -> None:
    await db.execute(
        update(SessionRow)
        .where(SessionRow.id == session_id, SessionRow.revoked_at.is_(None))
        .values(revoked_at=func.now())
    )
