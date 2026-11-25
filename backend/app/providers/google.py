import time
from dataclasses import dataclass
from functools import lru_cache
from typing import Any
from urllib.parse import urlencode

import httpx
import jwt

from app.core.settings import Settings, get_settings

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"
ISSUERS = ["https://accounts.google.com", "accounts.google.com"]
JWKS_TTL_SECONDS = 3600
JWKS_MIN_REFETCH_SECONDS = 60


class GoogleAuthError(Exception):
    """Google rejected the code or the ID token is not acceptable."""


@dataclass(frozen=True)
class GoogleIdentity:
    sub: str
    email: str
    name: str


def authorization_url(settings: Settings, state: str) -> str:
    query = urlencode(
        {
            "client_id": settings.google_client_id,
            "redirect_uri": settings.google_redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "prompt": "select_account",
        }
    )
    return f"{AUTH_URL}?{query}"


class GoogleClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._keys: dict[str, Any] = {}
        self._fetched_at = 0.0

    async def exchange_code(self, code: str) -> str:
        """Trade the authorization code for an ID token."""
        data = {
            "code": code,
            "client_id": self._settings.google_client_id,
            "client_secret": self._settings.google_client_secret,
            "redirect_uri": self._settings.google_redirect_uri,
            "grant_type": "authorization_code",
        }
        try:
            async with httpx.AsyncClient(timeout=10) as http:
                response = await http.post(TOKEN_URL, data=data)
            response.raise_for_status()
            id_token = response.json().get("id_token")
        except (httpx.HTTPError, ValueError) as exc:
            raise GoogleAuthError("token exchange failed") from exc
        if not isinstance(id_token, str) or not id_token:
            raise GoogleAuthError("token response has no id_token")
        return id_token

    async def _fetch_jwks(self) -> list[dict[str, Any]]:
        async with httpx.AsyncClient(timeout=10) as http:
            response = await http.get(JWKS_URL)
        response.raise_for_status()
        keys = response.json()["keys"]
        return [k for k in keys if isinstance(k, dict)]

    async def _signing_key(self, kid: str) -> Any:
        now = time.monotonic()
        age = now - self._fetched_at
        stale = age > JWKS_TTL_SECONDS
        missing = kid not in self._keys and age > JWKS_MIN_REFETCH_SECONDS
        if stale or missing or not self._keys:
            try:
                jwks = await self._fetch_jwks()
            except (httpx.HTTPError, ValueError, KeyError) as exc:
                raise GoogleAuthError("could not load Google signing keys") from exc
            self._keys = {str(k["kid"]): jwt.PyJWK(k).key for k in jwks if "kid" in k}
            self._fetched_at = now
        key = self._keys.get(kid)
        if key is None:
            raise GoogleAuthError("unknown signing key")
        return key

    async def verify_id_token(self, id_token: str) -> GoogleIdentity:
        try:
            kid = jwt.get_unverified_header(id_token).get("kid")
            if not isinstance(kid, str):
                raise GoogleAuthError("ID token has no key id")
            key = await self._signing_key(kid)
            claims = jwt.decode(
                id_token,
                key,
                algorithms=["RS256"],
                audience=self._settings.google_client_id,
                issuer=ISSUERS,
                options={"require": ["exp", "iss", "aud", "sub"]},
            )
        except jwt.PyJWTError as exc:
            raise GoogleAuthError("invalid ID token") from exc
        email = claims.get("email")
        verified = claims.get("email_verified")
        if not isinstance(email, str) or not email or verified not in (True, "true"):
            raise GoogleAuthError("email is missing or not verified")
        name = claims.get("name")
        return GoogleIdentity(
            sub=str(claims["sub"]),
            email=email.strip().lower(),
            name=name.strip() if isinstance(name, str) else "",
        )


@lru_cache
def _shared_client() -> GoogleClient:
    return GoogleClient(get_settings())


def get_google_client() -> GoogleClient:
    """FastAPI dependency; tests override it with a fake."""
    return _shared_client()
