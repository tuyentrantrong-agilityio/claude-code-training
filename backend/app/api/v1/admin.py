import uuid
from datetime import UTC, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Response
from pydantic import BaseModel, EmailStr
from sqlalchemy import Select, func, select, update
from sqlalchemy.exc import IntegrityError

from app.api.deps import Db, OwnerCsrfSession, OwnerSession
from app.core.errors import AppError
from app.core.settings import get_settings
from app.db.models.public import Invite, Membership, User
from app.db.models.public import Session as SessionRow

router = APIRouter(prefix="/admin", tags=["admin"])

Role = Literal["owner", "member"]


class MemberOut(BaseModel):
    user_id: str
    email: str
    name: str
    role: Role


class InviteOut(BaseModel):
    id: str
    email: str
    role: Role
    expires_at: datetime
    created_at: datetime


class RoleBody(BaseModel):
    role: Role


class InviteBody(BaseModel):
    email: EmailStr
    role: Role


def _member(user: User, role: str) -> MemberOut:
    return MemberOut(
        user_id=str(user.id),
        email=user.email,
        name=user.name,
        role="owner" if role == "owner" else "member",
    )


def _invite(invite: Invite) -> InviteOut:
    return InviteOut(
        id=str(invite.id),
        email=invite.email,
        role="owner" if invite.role == "owner" else "member",
        expires_at=invite.expires_at,
        created_at=invite.created_at,
    )


@router.get("/members")
async def list_members(current: OwnerSession, db: Db) -> list[MemberOut]:
    stmt = (
        select(User, Membership.role)
        .join(Membership, Membership.user_id == User.id)
        .where(Membership.organization_id == current.organization.id)
        .order_by(Membership.created_at, User.email)
    )
    return [_member(user, role) for user, role in (await db.execute(stmt)).all()]


async def _locked_membership(
    db: Db, organization_id: uuid.UUID, user_id: uuid.UUID
) -> tuple[Membership, int]:
    """Lock the org's owner rows and the target; return (target, owner count)."""
    rows = (
        await db.scalars(
            select(Membership)
            .where(Membership.organization_id == organization_id)
            .with_for_update()
        )
    ).all()
    target = next((m for m in rows if m.user_id == user_id), None)
    if target is None:
        raise AppError("member_not_found", "Member not found", status_code=404)
    return target, sum(1 for m in rows if m.role == "owner")


@router.patch("/members/{user_id}")
async def change_role(
    user_id: uuid.UUID, body: RoleBody, current: OwnerCsrfSession, db: Db
) -> MemberOut:
    target, owners = await _locked_membership(db, current.organization.id, user_id)
    if target.role == "owner" and body.role != "owner" and owners <= 1:
        raise AppError("last_owner", "An organization needs at least one owner", status_code=409)
    target.role = body.role
    user = await db.get(User, user_id)
    assert user is not None
    await db.commit()
    return _member(user, body.role)


@router.delete("/members/{user_id}", status_code=204)
async def remove_member(user_id: uuid.UUID, current: OwnerCsrfSession, db: Db) -> Response:
    target, owners = await _locked_membership(db, current.organization.id, user_id)
    if target.role == "owner" and owners <= 1:
        raise AppError("last_owner", "An organization needs at least one owner", status_code=409)
    await db.delete(target)
    await db.execute(
        update(SessionRow)
        .where(
            SessionRow.user_id == user_id,
            SessionRow.organization_id == current.organization.id,
            SessionRow.revoked_at.is_(None),
        )
        .values(revoked_at=func.now())
    )
    await db.commit()
    return Response(status_code=204)


def _open_invites(organization_id: uuid.UUID) -> Select[Invite]:
    return select(Invite).where(
        Invite.organization_id == organization_id,
        Invite.accepted_at.is_(None),
        Invite.revoked_at.is_(None),
    )


@router.get("/invites")
async def list_invites(current: OwnerSession, db: Db) -> list[InviteOut]:
    stmt = (
        _open_invites(current.organization.id)
        .where(Invite.expires_at > func.now())
        .order_by(Invite.created_at)
    )
    return [_invite(i) for i in (await db.scalars(stmt)).all()]


@router.post("/invites", status_code=201)
async def create_invite(body: InviteBody, current: OwnerCsrfSession, db: Db) -> InviteOut:
    email = body.email.strip().lower()
    org_id = current.organization.id
    member = await db.scalar(
        select(Membership.user_id)
        .join(User, User.id == Membership.user_id)
        .where(Membership.organization_id == org_id, User.email == email)
    )
    if member is not None:
        raise AppError("already_member", "That person is already a member", status_code=409)
    now = datetime.now(UTC)
    for existing in (await db.scalars(_open_invites(org_id).where(Invite.email == email))).all():
        if existing.expires_at > now:
            raise AppError(
                "invite_exists", "A pending invite already exists for that email", status_code=409
            )
        existing.revoked_at = now  # expired: free the unique slot
    await db.flush()
    invite = Invite(
        organization_id=org_id,
        email=email,
        role=body.role,
        invited_by=current.user.id,
        expires_at=now + timedelta(days=get_settings().invite_ttl_days),
    )
    db.add(invite)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise AppError(
            "invite_exists", "A pending invite already exists for that email", status_code=409
        ) from exc
    await db.refresh(invite)
    return _invite(invite)


@router.delete("/invites/{invite_id}", status_code=204)
async def revoke_invite(invite_id: uuid.UUID, current: OwnerCsrfSession, db: Db) -> Response:
    invite = await db.scalar(_open_invites(current.organization.id).where(Invite.id == invite_id))
    if invite is None:
        raise AppError("invite_not_found", "Invite not found", status_code=404)
    invite.revoked_at = datetime.now(UTC)
    await db.commit()
    return Response(status_code=204)
