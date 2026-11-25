import hashlib
import hmac
import secrets
import time

STATE_TTL_SECONDS = 600


def _sign(secret_key: str, message: str) -> str:
    return hmac.new(secret_key.encode(), message.encode(), hashlib.sha256).hexdigest()


def new_state(secret_key: str, now: float | None = None) -> tuple[str, str]:
    """Return (state, cookie_value). The cookie is "nonce.issued_at.signature"."""
    nonce = secrets.token_urlsafe(24)
    issued = str(int(time.time() if now is None else now))
    signature = _sign(secret_key, f"state:{nonce}.{issued}")
    return nonce, f"{nonce}.{issued}.{signature}"


def verify_state(
    secret_key: str, cookie_value: str | None, state: str | None, now: float | None = None
) -> bool:
    if not cookie_value or not state:
        return False
    parts = cookie_value.split(".")
    if len(parts) != 3:
        return False
    nonce, issued, signature = parts
    expected = _sign(secret_key, f"state:{nonce}.{issued}")
    if not hmac.compare_digest(signature, expected):
        return False
    if not issued.isdigit():
        return False
    age = (time.time() if now is None else now) - int(issued)
    if age < 0 or age > STATE_TTL_SECONDS:
        return False
    return hmac.compare_digest(nonce, state)


def new_session_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def csrf_token(secret_key: str, session_id: str) -> str:
    return _sign(secret_key, f"csrf:{session_id}")


def csrf_matches(secret_key: str, session_id: str, supplied: str | None) -> bool:
    if not supplied:
        return False
    return hmac.compare_digest(supplied, csrf_token(secret_key, session_id))
