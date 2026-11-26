import time
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from app.core.settings import Settings
from app.providers.google import GoogleAuthError, GoogleClient, authorization_url

PRIVATE = rsa.generate_private_key(public_exponent=65537, key_size=2048)


def make_client() -> GoogleClient:
    client = GoogleClient(Settings(google_client_id="cid", google_client_secret="s"))

    async def fake_jwks() -> list[dict[str, Any]]:
        jwk = jwt.algorithms.RSAAlgorithm.to_jwk(PRIVATE.public_key(), as_dict=True)
        return [{**jwk, "kid": "k1", "alg": "RS256", "use": "sig"}]

    client._fetch_jwks = fake_jwks  # type: ignore[method-assign]
    return client


def token(**overrides: Any) -> str:
    claims: dict[str, Any] = {
        "iss": "https://accounts.google.com",
        "aud": "cid",
        "sub": "123",
        "email": "A@Example.com",
        "email_verified": True,
        "name": "Ann",
        "exp": int(time.time()) + 300,
    }
    claims.update(overrides)
    return jwt.encode(claims, PRIVATE, algorithm="RS256", headers={"kid": "k1"})


async def test_valid_token() -> None:
    identity = await make_client().verify_id_token(token())
    assert (identity.sub, identity.email, identity.name) == ("123", "a@example.com", "Ann")


@pytest.mark.parametrize(
    "overrides",
    [
        {"iss": "https://evil.example"},
        {"aud": "other"},
        {"exp": int(time.time()) - 10},
        {"email_verified": False},
        {"email": None},
    ],
)
async def test_invalid_tokens(overrides: dict[str, Any]) -> None:
    with pytest.raises(GoogleAuthError):
        await make_client().verify_id_token(token(**overrides))


async def test_unknown_key_and_garbage() -> None:
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    forged = jwt.encode({"sub": "1"}, other, algorithm="RS256", headers={"kid": "k1"})
    with pytest.raises(GoogleAuthError):
        await make_client().verify_id_token(forged)
    with pytest.raises(GoogleAuthError):
        await make_client().verify_id_token("not-a-jwt")


def test_authorization_url() -> None:
    url = authorization_url(Settings(google_client_id="cid"), "st")
    assert "client_id=cid" in url and "state=st" in url and "response_type=code" in url
