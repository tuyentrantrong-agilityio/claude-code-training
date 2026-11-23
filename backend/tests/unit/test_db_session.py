import pytest
from httpx import ASGITransport, AsyncClient

from app.db.session import tenant_session, validate_schema_name
from app.main import app


def test_valid_schema_name() -> None:
    assert validate_schema_name("org_0123456789ab") == "org_0123456789ab"


@pytest.mark.parametrize(
    "name",
    [
        "public",
        "org_0123456789AB",
        "org_0123456789a",
        "org_0123456789abc",
        'org_0123456789ab"; DROP SCHEMA public',
        "org_0123456789ab\n",
        "",
    ],
)
def test_invalid_schema_name(name: str) -> None:
    with pytest.raises(ValueError):
        validate_schema_name(name)


async def test_tenant_session_rejects_bad_name() -> None:
    with pytest.raises(ValueError):
        async with tenant_session("public"):
            pass


async def test_ready_returns_503_when_db_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    async def broken() -> None:
        raise ConnectionError("db down")

    monkeypatch.setattr("app.api.v1.health.ping", broken)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/health/ready")

    assert response.status_code == 503
    error = response.json()["error"]
    assert error["code"] == "database_unavailable"
    assert "db down" not in response.text


async def test_ready_returns_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fine() -> None:
        return None

    monkeypatch.setattr("app.api.v1.health.ping", fine)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/health/ready")

    assert response.json() == {"status": "ok", "database": "ok"}
