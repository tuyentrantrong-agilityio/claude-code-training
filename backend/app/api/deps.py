from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.security import csrf_matches, hash_token
from app.core.settings import get_settings
from app.db.models.public import Membership, Organization, User
from app.db.models.public import Session as SessionRow
from app.db.session import get_public_session

SESSION_COOKIE = "recapz_session"
CSRF_HEADER = "X-CSRF-Token"

Db = Annotated[AsyncSession, Depends(get_public_session)]


@dataclass(frozen=True)
class CurrentSession:
    user: User
    organization: Organization
    role: str
    schema_name: str
    session_id: str


def not_signed_in() -> AppError:
    return AppError("not_signed_in", "You are not signed in", status_code=401)


async def get_current_session(request: Request, db: Db) -> CurrentSession:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise not_signed_in()
    session_id = hash_token(token)
    stmt = (
        select(User, Organization, Membership.role)
        .select_from(SessionRow)
        .join(User, User.id == SessionRow.user_id)
        .join(Organization, Organization.id == SessionRow.organization_id)
        .join(
            Membership,
            (Membership.user_id == SessionRow.user_id)
            & (Membership.organization_id == SessionRow.organization_id),
        )
        .where(
            SessionRow.id == session_id,
            SessionRow.revoked_at.is_(None),
            SessionRow.expires_at > func.now(),
        )
    )
    row = (await db.execute(stmt)).first()
    if row is None:
        raise not_signed_in()
    user, organization, role = row
    return CurrentSession(user, organization, role, organization.schema_name, session_id)


Current = Annotated[CurrentSession, Depends(get_current_session)]


async def require_csrf(request: Request, current: Current) -> CurrentSession:
    supplied = request.headers.get(CSRF_HEADER)
    if not csrf_matches(get_settings().secret_key, current.session_id, supplied):
        raise AppError("csrf_failed", "Missing or invalid CSRF token", status_code=403)
    return current


async def require_owner(current: Current) -> CurrentSession:
    if current.role != "owner":
        raise AppError("owner_only", "Only owners can do this", status_code=403)
    return current


async def require_owner_csrf(
    request: Request, current: Annotated[CurrentSession, Depends(require_owner)]
) -> CurrentSession:
    return await require_csrf(request, current)


CsrfSession = Annotated[CurrentSession, Depends(require_csrf)]
OwnerSession = Annotated[CurrentSession, Depends(require_owner)]
OwnerCsrfSession = Annotated[CurrentSession, Depends(require_owner_csrf)]
