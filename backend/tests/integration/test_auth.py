from datetime import UTC, datetime

from httpx import AsyncClient
from sqlalchemy import func, select

from app.api.v1.auth import STATE_COOKIE
from app.core.security import hash_token, new_state
from app.core.settings import get_settings
from app.db.models.public import Invite, Membership, User
from app.db.models.public import Session as SessionRow
from app.db.session import get_sessionmaker
from tests.integration.conftest import (
    FakeGoogle,
    add_invite,
    add_member,
    csrf_headers,
    make_org,
    sign_in,
    use_session,
)


async def count(model: type) -> int:
    async with get_sessionmaker()() as db:
        return int(await db.scalar(select(func.count()).select_from(model)) or 0)


async def test_start_redirects_to_google(client: AsyncClient, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "cid")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "secret")
    get_settings.cache_clear()
    try:
        response = await client.get("/api/v1/auth/google/start")
    finally:
        get_settings.cache_clear()
    assert response.status_code == 302
    location = response.headers["location"]
    assert location.startswith("https://accounts.google.com/o/oauth2/v2/auth?")
    assert "scope=openid+email+profile" in location
    assert "prompt=select_account" in location
    assert "recapz_oauth_state" in response.headers["set-cookie"]


async def test_start_without_config_is_503(client: AsyncClient) -> None:
    response = await client.get("/api/v1/auth/google/start")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "google_not_configured"


async def test_invited_email_creates_user_membership_and_session(
    client: AsyncClient, google: FakeGoogle
) -> None:
    org = await make_org()
    await add_invite(org, "new@example.com", "member")
    response = await sign_in(client, google, "new@example.com")
    assert response.status_code == 302
    assert response.headers["location"] == "http://localhost:5173/home"
    cookie = response.headers["set-cookie"]
    assert "recapz_session=" in cookie and "HttpOnly" in cookie and "SameSite=lax" in cookie
    me = (await client.get("/api/v1/me")).json()
    assert me["user"]["email"] == "new@example.com"
    assert me["organization"]["name"] == "Acme"
    assert me["role"] == "member"
    async with get_sessionmaker()() as db:
        invite = await db.scalar(select(Invite))
        assert invite is not None and invite.accepted_at is not None
        user = await db.scalar(select(User).where(User.email == "new@example.com"))
        assert user is not None and user.google_sub == "sub-new@example.com"
        assert user.last_sign_in_at is not None
        sessions = (await db.scalars(select(SessionRow))).all()
        assert len(sessions) == 1
        assert sessions[0].id == hash_token(client.cookies["recapz_session"])


async def test_existing_member_signs_in(client: AsyncClient, google: FakeGoogle) -> None:
    org = await make_org()
    await add_member(org, "owner@example.com", "owner")
    response = await sign_in(client, google, "Owner@Example.com")
    assert response.headers["location"].endswith("/home")
    me = (await client.get("/api/v1/me")).json()
    assert me["role"] == "owner"
    assert me["user"]["name"] == "Test User"  # refreshed from Google


async def test_not_invited_creates_nothing(client: AsyncClient, google: FakeGoogle) -> None:
    await make_org()
    response = await sign_in(client, google, "stranger@example.com")
    assert response.status_code == 302
    assert response.headers["location"] == "http://localhost:5173/sign-in?error=not_invited"
    assert "recapz_session" not in client.cookies
    assert await count(User) == 0
    assert await count(Membership) == 0
    assert await count(SessionRow) == 0


async def test_expired_and_revoked_invites_are_rejected(
    client: AsyncClient, google: FakeGoogle
) -> None:
    org = await make_org()
    await add_invite(org, "late@example.com", expires_in_days=-1)
    invite_id = await add_invite(org, "gone@example.com")
    async with get_sessionmaker()() as db, db.begin():
        invite = await db.get(Invite, invite_id)
        assert invite is not None
        invite.revoked_at = datetime.now(UTC)
    for email in ("late@example.com", "gone@example.com"):
        response = await sign_in(client, google, email)
        assert response.headers["location"].endswith("error=not_invited")
    assert await count(User) == 0


async def test_bad_state_is_400(client: AsyncClient, google: FakeGoogle) -> None:
    code = google.allow("a@example.com")
    response = await client.get("/api/v1/auth/google/callback", params={"code": code, "state": "x"})
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "invalid_state"
    assert set(body["error"]) == {"code", "message", "details"}


async def test_google_failure_redirects(client: AsyncClient, google: FakeGoogle) -> None:
    state, cookie = new_state(get_settings().secret_key)
    response = await client.get(
        "/api/v1/auth/google/callback",
        params={"code": "unknown", "state": state},
        headers={"Cookie": f"{STATE_COOKIE}={cookie}"},
    )
    assert response.headers["location"].endswith("error=google_failed")


async def test_different_google_sub_is_rejected(client: AsyncClient, google: FakeGoogle) -> None:
    org = await make_org()
    await add_member(org, "a@example.com")
    await sign_in(client, google, "a@example.com")
    client.cookies.clear()
    code = google.allow("a@example.com", sub="other")
    state, cookie = new_state(get_settings().secret_key)
    response = await client.get(
        "/api/v1/auth/google/callback",
        params={"code": code, "state": state},
        headers={"Cookie": f"{STATE_COOKIE}={cookie}"},
    )
    assert response.headers["location"].endswith("error=not_invited")


async def test_me_requires_cookie(client: AsyncClient) -> None:
    response = await client.get("/api/v1/me")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "not_signed_in"


async def test_me_rejects_expired_session(client: AsyncClient, google: FakeGoogle) -> None:
    org = await make_org()
    await add_member(org, "a@example.com")
    await sign_in(client, google, "a@example.com")
    async with get_sessionmaker()() as db, db.begin():
        row = await db.scalar(select(SessionRow))
        assert row is not None
        row.expires_at = datetime.now(UTC)
    assert (await client.get("/api/v1/me")).status_code == 401


async def test_sign_out_revokes_session(client: AsyncClient, google: FakeGoogle) -> None:
    org = await make_org()
    await add_member(org, "a@example.com")
    await sign_in(client, google, "a@example.com")
    token = client.cookies["recapz_session"]
    headers = await csrf_headers(client)
    response = await client.post("/api/v1/auth/sign-out", headers=headers)
    assert response.status_code == 204
    assert "recapz_session" in response.headers["set-cookie"]
    async with get_sessionmaker()() as db:
        row = await db.get(SessionRow, hash_token(token))
        assert row is not None and row.revoked_at is not None
    use_session(client, token)
    assert (await client.get("/api/v1/me")).status_code == 401


async def test_sign_out_without_csrf_is_403(client: AsyncClient, google: FakeGoogle) -> None:
    org = await make_org()
    await add_member(org, "a@example.com")
    await sign_in(client, google, "a@example.com")
    response = await client.post("/api/v1/auth/sign-out")
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "csrf_failed"
    wrong = await client.post("/api/v1/auth/sign-out", headers={"X-CSRF-Token": "nope"})
    assert wrong.status_code == 403
    assert (await client.get("/api/v1/me")).status_code == 200
