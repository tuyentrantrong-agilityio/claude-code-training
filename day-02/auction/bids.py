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


STEP_LIMIT = 1000  # highest amount from which the larger step applies
SMALL_STEP, LARGE_STEP = 10, 50


def minimum_step(highest):
    return SMALL_STEP if highest < STEP_LIMIT else LARGE_STEP


def minimum_next_bid(highest):
    """Lowest amount a new bid may offer; 1 when the auction has no active bid."""
    return 1 if highest is None else highest + minimum_step(highest)


class BidTooLowError(ValueError):
    def __init__(self, minimum):
        super().__init__(f"bid must be at least {minimum}")
        self.minimum = minimum


def highest_bid(conn, auction_id):
    """Top active bid of an auction (highest amount, then earliest), or None."""
    return conn.execute(
        "SELECT id, amount FROM bids WHERE auction_id = ? AND status = 'active' "
        "ORDER BY amount DESC, created_at ASC, id ASC LIMIT 1",
        (auction_id,),
    ).fetchone()


def place_bid(conn, user_id, auction_id, amount, created_at, status="active"):
    """Store a bid. Raises BidTooLowError unless it reaches the minimum next bid.

    The check and the insert are one statement, so concurrent bids cannot both pass.
    The check is written as `existing > amount - step` so it cannot overflow.
    """
    cur = conn.execute(
        "INSERT INTO bids (user_id, auction_id, amount, status, created_at) "
        "SELECT ?, ?, ?, ?, ? WHERE NOT EXISTS ("
        "SELECT 1 FROM bids WHERE auction_id = ? AND status = 'active' AND amount > "
        "? - CASE WHEN amount < ? THEN ? ELSE ? END)",
        (user_id, auction_id, amount, status, created_at, auction_id, amount,
         STEP_LIMIT, SMALL_STEP, LARGE_STEP),
    )
    conn.commit()
    if cur.rowcount == 0:
        raise BidTooLowError(minimum_next_bid(highest_bid(conn, auction_id)["amount"]))
    return cur.lastrowid


def encode_cursor(created_at, bid_id):
    return base64.urlsafe_b64encode(
        json.dumps({"created_at": created_at, "id": bid_id}).encode()
    ).decode()


def decode_cursor(cursor):
    """Return (created_at, id). Raises ValueError for any malformed cursor."""
    try:
        data = json.loads(base64.urlsafe_b64decode(cursor.encode()))
        values = (data["created_at"], data["id"])
    except (ValueError, KeyError, TypeError) as exc:
        raise ValueError("invalid cursor") from exc
    if not all(type(v) is int and abs(v) <= 2**63 - 1 for v in values):
        raise ValueError("invalid cursor")
    return values


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
    for item in items:
        top = highest_bid(conn, item["auction_id"])
        if item["status"] != "active":
            item["standing"] = None
        else:
            item["standing"] = "winning" if top and top["id"] == item["id"] else "outbid"
    next_cursor = (
        encode_cursor(items[-1]["created_at"], items[-1]["id"])
        if len(items) == limit
        else None
    )
    return {"items": items, "next_cursor": next_cursor}
