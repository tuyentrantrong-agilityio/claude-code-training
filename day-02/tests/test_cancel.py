"""T-01: cancel_bid in the bids store (intent/2026-11-02-cancel-bid)."""
import os
import tempfile
import threading
import time
import unittest

from auction.bids import (
    BidNotActiveError, BidNotFoundError, CancelTooLateError, cancel_bid, connect, place_bid,
)

T = 1_700_000_000_000
MINUTE = 60_000


class CancelBidTest(unittest.TestCase):
    def setUp(self):
        self.conn = connect()

    def row(self, bid_id):
        return dict(self.conn.execute("SELECT * FROM bids WHERE id = ?", (bid_id,)).fetchone())

    def test_cancel_bid_returns_auction_id_and_keeps_row(self):
        place_bid(self.conn, 5, 7, 100, T)
        mine = place_bid(self.conn, 42, 7, 500, T)
        before = self.row(mine)
        self.assertEqual(cancel_bid(self.conn, mine, 42, T + MINUTE), 7)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM bids").fetchone()[0], 2)
        self.assertEqual(self.row(mine), {**before, "status": "cancelled"})

    def test_other_users_bid_any_status_or_age_is_not_found(self):
        others = place_bid(self.conn, 5, 7, 100, T, status="cancelled")
        with self.assertRaises(BidNotFoundError) as caught:
            cancel_bid(self.conn, others, 42, T + 60 * MINUTE)
        self.assertEqual(str(caught.exception), "bid not found")
        self.assertEqual(self.row(others)["status"], "cancelled")
        with self.assertRaises(BidNotFoundError):
            cancel_bid(self.conn, 999, 42, T)

    def test_not_active_checked_before_window(self):
        mine = place_bid(self.conn, 42, 7, 500, T, status="cancelled")
        with self.assertRaises(BidNotActiveError) as caught:
            cancel_bid(self.conn, mine, 42, T + 60 * MINUTE)
        self.assertEqual(str(caught.exception), "bid is not active")

    def test_other_non_active_status_is_not_active(self):
        mine = place_bid(self.conn, 42, 7, 500, T, status="won")
        before = self.row(mine)
        with self.assertRaises(BidNotActiveError):
            cancel_bid(self.conn, mine, 42, T)
        self.assertEqual(self.row(mine), before)


TOO_LATE = "too late to cancel: bids can only be cancelled within 5 minutes"
PLACED = 1_793_613_600_000  # 2026-11-02 10:00:00.000 UTC
WINDOW = 300_000


class CancelWindowTest(unittest.TestCase):
    def setUp(self):
        self.conn = connect()
        self.bid = place_bid(self.conn, 42, 8, 200, PLACED)

    def status(self):
        return self.conn.execute("SELECT status FROM bids WHERE id = ?", (self.bid,)).fetchone()["status"]

    def test_cancel_at_exactly_300000_ms_is_accepted(self):
        self.assertEqual(cancel_bid(self.conn, self.bid, 42, now_ms=PLACED + WINDOW), 8)
        self.assertEqual(self.status(), "cancelled")

    def test_cancel_one_ms_after_window_is_too_late(self):
        with self.assertRaises(CancelTooLateError) as caught:
            cancel_bid(self.conn, self.bid, 42, now_ms=PLACED + WINDOW + 1)
        self.assertEqual(str(caught.exception), TOO_LATE)
        self.assertEqual(self.status(), "active")

    def test_cancel_at_zero_ms_is_accepted(self):
        self.assertEqual(cancel_bid(self.conn, self.bid, 42, now_ms=PLACED), 8)
        self.assertEqual(self.status(), "cancelled")

    def test_created_at_later_than_now_is_inside_window(self):
        self.assertEqual(cancel_bid(self.conn, self.bid, 42, now_ms=PLACED - 1000), 8)
        self.assertEqual(self.status(), "cancelled")

    def test_now_ms_defaults_to_current_time(self):
        fresh = place_bid(self.conn, 42, 9, 100, int(time.time() * 1000))
        self.assertEqual(cancel_bid(self.conn, fresh, 42), 9)
        old = place_bid(self.conn, 42, 10, 100, int(time.time() * 1000) - WINDOW - 5000)
        with self.assertRaises(CancelTooLateError):
            cancel_bid(self.conn, old, 42)

    def test_not_found_and_not_active_come_before_too_late(self):
        late = PLACED + 60 * 60 * 1000
        with self.assertRaises(BidNotFoundError):
            cancel_bid(self.conn, self.bid, 5, now_ms=late)
        cancelled = place_bid(self.conn, 42, 11, 100, PLACED, status="cancelled")
        with self.assertRaises(BidNotActiveError):
            cancel_bid(self.conn, cancelled, 42, now_ms=late)
        with self.assertRaises(CancelTooLateError):
            cancel_bid(self.conn, self.bid, 42, now_ms=late)


class CancelRaceTest(unittest.TestCase):
    def test_two_simultaneous_cancels_on_one_file_database(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "bids.db")
            setup = connect(path)
            bid = place_bid(setup, 42, 11, 120, PLACED)
            setup.close()
            barrier = threading.Barrier(2, timeout=10)
            outcomes = []

            def worker():
                conn = connect(path)
                try:
                    barrier.wait()
                    outcomes.append(("ok", cancel_bid(conn, bid, 42, now_ms=PLACED + 60_000)))
                except BidNotActiveError as exc:
                    outcomes.append(("error", str(exc)))
                finally:
                    conn.close()

            threads = [threading.Thread(target=worker) for _ in range(2)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=20)
            self.assertEqual(sorted(outcomes), [("error", "bid is not active"), ("ok", 11)])
            check = connect(path)
            rows = [dict(r) for r in check.execute("SELECT id, status FROM bids")]
            check.close()
            self.assertEqual(rows, [{"id": bid, "status": "cancelled"}])


if __name__ == "__main__":
    unittest.main()
