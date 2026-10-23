"""Minimal bids store for the auction platform: GET /me/bids with cursor pagination.

created_at is stored as epoch milliseconds (INTEGER), the same precision the
real API exposes.
"""

import base64
import json
import sqlite3

MAX_LIMIT = 100

SCHEMA = """
CREATE TABLE IF NOT EXISTS bids (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL,
    auction_id  INTEGER NOT NULL,
    amount      INTEGER NOT NULL,
    status      TEXT    NOT NULL DEFAULT 'active',
    created_at  INTEGER NOT NULL
);
"""


def connect(path=":memory:"):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def place_bid(conn, user_id, auction_id, amount, created_at, status="active"):
    cur = conn.execute(
        "INSERT INTO bids (user_id, auction_id, amount, status, created_at) VALUES (?, ?, ?, ?, ?)",
        (user_id, auction_id, amount, status, created_at),
    )
    conn.commit()
    return cur.lastrowid


def encode_cursor(created_at, bid_id):
    return base64.urlsafe_b64encode(
        json.dumps({"created_at": created_at, "id": bid_id}).encode()
    ).decode()


def decode_cursor(cursor):
    data = json.loads(base64.urlsafe_b64decode(cursor.encode()))
    return data["created_at"], data["id"]


def list_my_bids(conn, user_id, limit=20, cursor=None):
    """Return one page of the user's bids, newest first.

    Response shape mirrors the API: {"items": [...], "next_cursor": str | None}.
    Raises ValueError unless 1 <= limit <= MAX_LIMIT.
    """
    if not 1 <= limit <= MAX_LIMIT:
        raise ValueError(f"limit must be between 1 and {MAX_LIMIT}")

    sql = (
        "SELECT id, auction_id, amount, status, created_at FROM bids WHERE user_id = ?"
    )
    params = [user_id]
    if cursor is not None:
        sql += " AND (created_at, id) < (?, ?)"
        params.extend(decode_cursor(cursor))

    sql += " ORDER BY created_at DESC, id DESC LIMIT ?"
    params.append(limit)

    items = [dict(r) for r in conn.execute(sql, params)]
    next_cursor = (
        encode_cursor(items[-1]["created_at"], items[-1]["id"])
        if len(items) == limit
        else None
    )
    return {"items": items, "next_cursor": next_cursor}
