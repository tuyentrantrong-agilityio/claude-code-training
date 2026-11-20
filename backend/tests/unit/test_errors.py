from httpx import ASGITransport, AsyncClient

from app.core.errors import AppError
from app.main import create_app


def _client() -> AsyncClient:
    app = create_app()

    @app.get("/boom")
    async def boom() -> None:
        raise AppError("not_found", "Thing missing", status_code=404, details={"id": 7})

    @app.get("/items/{item_id}")
    async def item(item_id: int) -> dict[str, int]:
        return {"id": item_id}

    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def test_app_error_uses_error_format() -> None:
    async with _client() as client:
        response = await client.get("/boom")

    assert response.status_code == 404
    assert response.json() == {
        "error": {"code": "not_found", "message": "Thing missing", "details": {"id": 7}}
    }


async def test_validation_error_returns_400() -> None:
    async with _client() as client:
        response = await client.get("/items/abc")

    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "validation_error"
    assert "message" in body["error"]
    assert "errors" in body["error"]["details"]
