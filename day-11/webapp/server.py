"""Tiny web UI over day-02/auction: python -m webapp.server (run from day-11/)."""
import json
import os
import re
import sqlite3
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse, urlsplit

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "day-02"))
from auction.bids import (  # noqa: E402
    SCHEMA, BidNotActiveError, BidNotFoundError, BidTooLowError, cancel_bid, list_my_bids,
    minimum_bid, place_bid,
)

USER = 42
MAX_VALUE = 2**63 - 1  # SQLite INTEGER limit
INDEX = os.path.join(os.path.dirname(__file__), "index.html")
# One raw path segment (not percent-decoded, may be empty) between the fixed parts.
MINIMUM_BID_PATH = re.compile(r"/api/auctions/([^/]*)/minimum-bid")
CANCEL_PATH = re.compile(r"/api/bids/([^/]*)/cancel")


def to_int(value):
    """Accept ints and digit strings only; floats and booleans are rejected."""
    if isinstance(value, (bool, float)):
        raise ValueError("not an integer")
    return int(value)


def parse_auction_id(segment):
    """Digits only, leading zeros allowed, value 1 to 2^63-1; else None.

    The length is checked before int(), which refuses strings over 4300 digits.
    """
    if not (segment.isascii() and segment.isdigit()):
        return None
    digits = segment.lstrip("0")
    if not digits or len(digits) > len(str(MAX_VALUE)):
        return None
    value = int(digits)
    return value if value <= MAX_VALUE else None


def request_path(target):
    """Path of a request target with ";params" kept (urlparse drops them).

    Only an absolute-form target ("http://host/path") has a host to remove; any other
    target, "//x/..." included, is a path as written.
    """
    if target.startswith(("http://", "https://")):
        return urlsplit(target).path
    return target.partition("?")[0]


def make_server(port=8000):
    # check_same_thread=False: the threaded server uses one connection.
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    # One shared connection: serialize use so rowcount/lastrowid are not mixed up.
    lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass

        def _send(self, status, body, ctype="application/json"):
            data = body if isinstance(body, bytes) else json.dumps(body).encode()
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            url = urlparse(self.path)
            if url.path == "/":
                with open(INDEX, "rb") as f:
                    return self._send(200, f.read(), "text/html; charset=utf-8")
            if url.path == "/api/bids":
                qs = parse_qs(url.query)
                try:
                    limit = int(qs.get("limit", ["20"])[0])
                    cursor = qs.get("cursor", [None])[0]
                    with lock:
                        page = list_my_bids(conn, USER, limit, cursor)
                    return self._send(200, page)
                except ValueError as exc:
                    return self._send(400, {"error": str(exc)})
            match = MINIMUM_BID_PATH.fullmatch(request_path(self.path))
            if match:
                auction_id = parse_auction_id(match.group(1))
                if auction_id is None:
                    return self._send(400, {"error": "invalid auction_id"})
                with lock:
                    return self._send(200, minimum_bid(conn, auction_id))
            self._send(404, {"error": "not found"})

        def do_HEAD(self):
            # The headers a GET 404 would send, without the body.
            body = json.dumps({"error": "not found"}).encode()
            self.send_response(404)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()

        def __getattr__(self, name):
            # Every method without its own do_X answers 404 JSON, not the default 501 page.
            if name.startswith("do_"):
                return lambda: self._send(404, {"error": "not found"})
            raise AttributeError(name)

        def _cancel(self, segment):
            bid_id = parse_auction_id(segment)  # same rules as an auction id
            if bid_id is None:
                return self._send(400, {"error": "invalid bid_id"})
            try:
                with lock:
                    auction_id = cancel_bid(conn, bid_id, USER, int(time.time() * 1000))
            except BidNotFoundError as exc:
                return self._send(404, {"error": str(exc)})
            except BidNotActiveError as exc:
                return self._send(409, {"error": str(exc)})
            self._send(200, {"id": bid_id, "auction_id": auction_id, "status": "cancelled"})

        def do_POST(self):
            cancel = CANCEL_PATH.fullmatch(request_path(self.path))
            if cancel:
                return self._cancel(cancel.group(1))
            if self.path != "/api/bids":
                return self._send(404, {"error": "not found"})
            try:
                size = int(self.headers.get("Content-Length", 0))
                body = json.loads(self.rfile.read(size))
                auction_id, amount = to_int(body["auction_id"]), to_int(body["amount"])
            except (ValueError, KeyError, TypeError, OverflowError):
                return self._send(400, {"error": "auction_id and amount must be integers"})
            if auction_id < 1 or amount < 1:
                return self._send(400, {"error": "auction_id and amount must be positive"})
            if auction_id > MAX_VALUE or amount > MAX_VALUE:
                return self._send(400, {"error": "auction_id and amount are too large"})
            now = int(time.time() * 1000)
            try:
                with lock:
                    bid_id = place_bid(conn, USER, auction_id, amount, now)
            except BidTooLowError as exc:
                return self._send(409, {"error": str(exc)})
            self._send(201, {"id": bid_id})

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.db, server.db_lock = conn, lock  # lets tests seed bids from other users
    return server


def main():
    server = make_server(8000)
    print("Serving on http://127.0.0.1:8000")
    server.serve_forever()


if __name__ == "__main__":
    main()
