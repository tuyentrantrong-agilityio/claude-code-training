from fastapi import APIRouter

from app.api.deps import Current
from app.db.session import tenant_session
from app.services import home as svc

router = APIRouter(prefix="/home", tags=["home"])


@router.get("")
async def get_home(current: Current) -> svc.HomeOut:
    async with tenant_session(current.schema_name) as session:
        return await svc.get_home(session, current.user.id)
