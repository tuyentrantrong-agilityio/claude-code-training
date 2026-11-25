import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import RedirectResponse

from app.api.deps import SESSION_COOKIE, CsrfSession, Db
from app.core.errors import AppError
from app.core.security import STATE_TTL_SECONDS, new_state, verify_state
from app.core.settings import Settings, get_settings
from app.providers.google import (
    GoogleAuthError,
    GoogleClient,
    authorization_url,
    get_google_client,
)
from app.services import auth as auth_service

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger(__name__)

STATE_COOKIE = "recapz_oauth_state"
GOOGLE_PATH = "/api/v1/auth/google"

SettingsDep = Annotated[Settings, Depends(get_settings)]
GoogleDep = Annotated[GoogleClient, Depends(get_google_client)]


def _secure(settings: Settings) -> bool:
    return settings.app_env != "development"


def _sign_in_redirect(settings: Settings, error: str) -> RedirectResponse:
    response = RedirectResponse(f"{settings.frontend_url}/sign-in?error={error}", status_code=302)
    response.delete_cookie(STATE_COOKIE, path=GOOGLE_PATH)
    return response


@router.get("/google/start")
async def google_start(settings: SettingsDep) -> RedirectResponse:
    if not settings.google_client_id or not settings.google_client_secret:
        raise AppError("google_not_configured", "Google sign-in is not configured", status_code=503)
    state, cookie_value = new_state(settings.secret_key)
    response = RedirectResponse(authorization_url(settings, state), status_code=302)
    response.set_cookie(
        STATE_COOKIE,
        cookie_value,
        max_age=STATE_TTL_SECONDS,
        httponly=True,
        secure=_secure(settings),
        samesite="lax",
        path=GOOGLE_PATH,
    )
    return response


@router.get("/google/callback")
async def google_callback(
    request: Request,
    db: Db,
    settings: SettingsDep,
    google: GoogleDep,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    cookie_value = request.cookies.get(STATE_COOKIE)
    if not verify_state(settings.secret_key, cookie_value, state):
        raise AppError("invalid_state", "Sign-in state is missing or expired", status_code=400)
    if error or not code:
        return _sign_in_redirect(settings, "google_failed")
    try:
        identity = await google.verify_id_token(await google.exchange_code(code))
    except GoogleAuthError as exc:
        logger.warning("google sign-in rejected: %s", exc)
        return _sign_in_redirect(settings, "google_failed")
    ttl = settings.session_ttl_days
    token = await auth_service.sign_in(db, identity, request.headers.get("user-agent"), ttl)
    if token is None:
        await db.rollback()
        return _sign_in_redirect(settings, "not_invited")
    await db.commit()
    response = RedirectResponse(f"{settings.frontend_url}/home", status_code=302)
    response.delete_cookie(STATE_COOKIE, path=GOOGLE_PATH)
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=ttl * 86400,
        httponly=True,
        secure=_secure(settings),
        samesite="lax",
        path="/",
    )
    return response


@router.post("/sign-out", status_code=204)
async def sign_out(current: CsrfSession, db: Db, settings: SettingsDep) -> Response:
    await auth_service.revoke_session(db, current.session_id)
    await db.commit()
    response = Response(status_code=204)
    response.delete_cookie(
        SESSION_COOKIE, path="/", httponly=True, secure=_secure(settings), samesite="lax"
    )
    return response
