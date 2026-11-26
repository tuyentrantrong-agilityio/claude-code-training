import pytest

from app.core.security import (
    STATE_TTL_SECONDS,
    csrf_matches,
    csrf_token,
    hash_token,
    new_session_token,
    new_state,
    verify_state,
)
from app.core.settings import DEV_SECRET_KEY, Settings

KEY = "unit-test-key"


def test_state_round_trip() -> None:
    state, cookie = new_state(KEY, now=1000)
    assert verify_state(KEY, cookie, state, now=1001)


def test_state_rejects_mismatch_tamper_and_expiry() -> None:
    state, cookie = new_state(KEY, now=1000)
    assert not verify_state(KEY, cookie, "other", now=1001)
    assert not verify_state(KEY, None, state, now=1001)
    assert not verify_state(KEY, cookie, None, now=1001)
    assert not verify_state("another-key", cookie, state, now=1001)
    nonce, issued, sig = cookie.split(".")
    assert not verify_state(KEY, f"{nonce}.{int(issued) + 1}.{sig}", state, now=1001)
    assert not verify_state(KEY, "garbage", state, now=1001)
    assert not verify_state(KEY, cookie, state, now=1000 + STATE_TTL_SECONDS + 1)


def test_csrf_token_is_bound_to_session_and_key() -> None:
    token = csrf_token(KEY, "session-a")
    assert csrf_matches(KEY, "session-a", token)
    assert not csrf_matches(KEY, "session-b", token)
    assert not csrf_matches("other", "session-a", token)
    assert not csrf_matches(KEY, "session-a", None)
    assert not csrf_matches(KEY, "session-a", "")


def test_session_tokens_are_random_and_hashed() -> None:
    a, b = new_session_token(), new_session_token()
    assert a != b and len(a) >= 43
    assert hash_token(a) == hash_token(a) != a
    assert len(hash_token(a)) == 64


def test_settings_secret_key_rules() -> None:
    assert Settings(app_env="development", secret_key="").secret_key == DEV_SECRET_KEY
    with pytest.raises(ValueError):
        Settings(app_env="production", secret_key="")
    assert Settings(app_env="production", secret_key="x").secret_key == "x"
