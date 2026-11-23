import logging

from fastapi import APIRouter

from app.core.errors import AppError
from app.db.session import ping

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready")
async def ready() -> dict[str, str]:
    try:
        await ping()
    except Exception as exc:
        logger.warning("database check failed: %s", type(exc).__name__)
        raise AppError("database_unavailable", "Database is unavailable", status_code=503) from exc
    return {"status": "ok", "database": "ok"}
