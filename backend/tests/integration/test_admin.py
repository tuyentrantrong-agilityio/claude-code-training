import uuid

from httpx import AsyncClient
from sqlalchemy import select

from app.db.models.public import Invite, Membership
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


async def owner_client(client: AsyncClient, google: FakeGoogle):  # type: ignore[no-untyped-def]
    org = await make_org()
    owner_id = await add_member(org, "owner@example.com", "owner")
    await sign_in(client, google, "owner@example.com")
    return org, owner_id, await csrf_headers(client)


async def test_member_gets_owner_only(client: AsyncClient, google: FakeGoogle) -> None:
    org = await make_org()
    await add_member(org, "m@example.com", "member")
    await sign_in(client, google, "m@example.com")
    headers = await csrf_headers(client)
    for response in (
        await client.get("/api/v1/admin/members"),
        await client.get("/api/v1/admin/invites"),
        await client.post(
            "/api/v1/admin/invites",
            json={"email": "x@example.com", "role": "member"},
            headers=headers,
        ),
    ):
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "owner_only"


async def test_admin_requires_sign_in(client: AsyncClient) -> None:
    assert (await client.get("/api/v1/admin/members")).status_code == 401


async def test_list_members(client: AsyncClient, google: FakeGoogle) -> None:
    org, _, _ = await owner_client(client, google)
    await add_member(org, "m@example.com")
    rows = (await client.get("/api/v1/admin/members")).json()
    assert {(r["email"], r["role"]) for r in rows} == {
        ("owner@example.com", "owner"),
        ("m@example.com", "member"),
    }


async def test_invite_create_duplicate_and_revoke(client: AsyncClient, google: FakeGoogle) -> None:
    org, _, headers = await owner_client(client, google)
    body = {"email": "New@Example.com", "role": "member"}
    missing = await client.post("/api/v1/admin/invites", json=body)
    assert missing.status_code == 403 and missing.json()["error"]["code"] == "csrf_failed"
    created = await client.post("/api/v1/admin/invites", json=body, headers=headers)
    assert created.status_code == 201
    invite = created.json()
    assert invite["email"] == "new@example.com" and invite["role"] == "member"
    dup = await client.post("/api/v1/admin/invites", json=body, headers=headers)
    assert dup.status_code == 409 and dup.json()["error"]["code"] == "invite_exists"
    listed = (await client.get("/api/v1/admin/invites")).json()
    assert [i["id"] for i in listed] == [invite["id"]]
    revoked = await client.delete(f"/api/v1/admin/invites/{invite['id']}", headers=headers)
    assert revoked.status_code == 204
    assert (await client.get("/api/v1/admin/invites")).json() == []
    again = await client.delete(f"/api/v1/admin/invites/{invite['id']}", headers=headers)
    assert again.status_code == 404
    recreated = await client.post("/api/v1/admin/invites", json=body, headers=headers)
    assert recreated.status_code == 201


async def test_invite_already_member_and_bad_email(client: AsyncClient, google: FakeGoogle) -> None:
    org, _, headers = await owner_client(client, google)
    await add_member(org, "m@example.com")
    response = await client.post(
        "/api/v1/admin/invites", json={"email": "M@example.com", "role": "member"}, headers=headers
    )
    assert response.status_code == 409 and response.json()["error"]["code"] == "already_member"
    bad = await client.post(
        "/api/v1/admin/invites", json={"email": "nope", "role": "member"}, headers=headers
    )
    assert bad.status_code == 400 and bad.json()["error"]["code"] == "validation_error"


async def test_expired_invite_can_be_replaced(client: AsyncClient, google: FakeGoogle) -> None:
    org, _, headers = await owner_client(client, google)
    await add_invite(org, "old@example.com", expires_in_days=-1)
    response = await client.post(
        "/api/v1/admin/invites", json={"email": "old@example.com", "role": "owner"}, headers=headers
    )
    assert response.status_code == 201
    async with get_sessionmaker()() as db:
        open_rows = (await db.scalars(select(Invite).where(Invite.revoked_at.is_(None)))).all()
        assert len(open_rows) == 1 and open_rows[0].role == "owner"


async def test_last_owner_is_protected(client: AsyncClient, google: FakeGoogle) -> None:
    org, owner_id, headers = await owner_client(client, google)
    demote = await client.patch(
        f"/api/v1/admin/members/{owner_id}", json={"role": "member"}, headers=headers
    )
    assert demote.status_code == 409 and demote.json()["error"]["code"] == "last_owner"
    remove = await client.delete(f"/api/v1/admin/members/{owner_id}", headers=headers)
    assert remove.status_code == 409 and remove.json()["error"]["code"] == "last_owner"
    other = await add_member(org, "second@example.com", "member")
    promote = await client.patch(
        f"/api/v1/admin/members/{other}", json={"role": "owner"}, headers=headers
    )
    assert promote.status_code == 200 and promote.json()["role"] == "owner"
    demote = await client.patch(
        f"/api/v1/admin/members/{owner_id}", json={"role": "member"}, headers=headers
    )
    assert demote.status_code == 200


async def test_unknown_member_is_404(client: AsyncClient, google: FakeGoogle) -> None:
    _, _, headers = await owner_client(client, google)
    response = await client.delete(f"/api/v1/admin/members/{uuid.uuid4()}", headers=headers)
    assert response.status_code == 404


async def test_removing_member_revokes_their_sessions(
    client: AsyncClient, google: FakeGoogle
) -> None:
    org, _, headers = await owner_client(client, google)
    member_id = await add_member(org, "m@example.com")
    owner_cookie = client.cookies["recapz_session"]
    await sign_in(client, google, "m@example.com")
    member_cookie = client.cookies["recapz_session"]
    assert member_cookie != owner_cookie
    assert (await client.get("/api/v1/me")).status_code == 200

    use_session(client, owner_cookie)
    response = await client.delete(f"/api/v1/admin/members/{member_id}", headers=headers)
    assert response.status_code == 204

    use_session(client, member_cookie)
    assert (await client.get("/api/v1/me")).status_code == 401
    async with get_sessionmaker()() as db:
        memberships = (await db.scalars(select(Membership))).all()
        assert [m.user_id for m in memberships] != [member_id]
        assert all(m.user_id != member_id for m in memberships)
        revoked = (
            await db.scalars(select(SessionRow).where(SessionRow.user_id == member_id))
        ).all()
        assert revoked and all(s.revoked_at is not None for s in revoked)
