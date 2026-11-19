"""Start the day-11 web app with demo data so a browser run has something to show.

Usage: python .claude/skills/evidence/seed_server.py [port]   (default 8010)

User 42 is the fixed user of the web UI. The competing bid from user 5 is
inserted straight into the database because the UI cannot act as another user.
"""

import os
import sqlite3
import sys
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "day-11"))
sys.path.insert(0, os.path.join(ROOT, "day-02"))

import webapp.server as srv  # noqa: E402
from auction.bids import place_bid  # noqa: E402

NOW = int(time.time() * 1000)
T = NOW - 60_000  # one minute old: inside the 5 minute cancel window while a run lasts


def seed(conn):
    place_bid(conn, 42, 7, 100, T)
    place_bid(conn, 5, 7, 150, T + 1)  # beats user 42 on auction 7
    place_bid(conn, 42, 8, 300, T + 2)  # user 42 winning on auction 8
    place_bid(conn, 42, 9, 80, T + 3)
    place_bid(conn, 42, 9, 120, T + 4)  # own higher bid, the older one is outbid
    place_bid(conn, 42, 11, 60, T + 5, status="cancelled")  # no standing
    place_bid(conn, 42, 12, 40, NOW - 6 * 60_000)  # six minutes old: too late to cancel


def main(port):
    captured = []
    real_connect = sqlite3.connect

    def capture(*args, **kwargs):
        conn = real_connect(*args, **kwargs)
        captured.append(conn)
        return conn

    srv.sqlite3.connect = capture
    server = srv.make_server(port)
    seed(captured[0])
    print(f"serving on http://127.0.0.1:{port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 8010)
