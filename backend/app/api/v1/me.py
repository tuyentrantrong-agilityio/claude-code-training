from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from app.api.deps import Current
from app.core.security import csrf_token
from app.core.settings import get_settings

router = APIRouter(tags=["me"])


class UserOut(BaseModel):
    id: str
    email: str
    name: str


class OrganizationOut(BaseModel):
    id: str
    name: str


class MeOut(BaseModel):
    user: UserOut
    organization: OrganizationOut
    role: Literal["owner", "member"]
    csrf_token: str


@router.get("/me")
async def me(current: Current) -> MeOut:
    return MeOut(
        user=UserOut(id=str(current.user.id), email=current.user.email, name=current.user.name),
        organization=OrganizationOut(
            id=str(current.organization.id), name=current.organization.name
        ),
        role="owner" if current.role == "owner" else "member",
        csrf_token=csrf_token(get_settings().secret_key, current.session_id),
    )
