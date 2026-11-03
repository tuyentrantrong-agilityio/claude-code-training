"""T-01 to T-03: cancel_bid in the bids store, its 5 minute window and the auction afterwards (intent/2026-11-02-cancel-bid)."""
import os
import tempfile
import threading
import time
import unittest

from auction.bids import (
    BidNotActiveError, BidNotFoundError, CancelTooLateError, cancel_bid, connect, highest_bid,
    list_my_bids, minimum_bid, place_bid,
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
        row = self.conn.execute("SELECT status FROM bids WHERE id = ?", (fresh,)).fetchone()
        self.assertEqual(row["status"], "cancelled")
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


class RecalculationTest(unittest.TestCase):
    """T-03: after a cancel the auction is computed as if the bid had never been placed."""

    def setUp(self):
        self.conn = connect()

    def insert(self, user, auction, amount, created_at):
        # Straight into the store: place_bid refuses an equal amount, old data may hold ties.
        cur = self.conn.execute(
            "INSERT INTO bids (user_id, auction_id, amount, status, created_at) VALUES (?, ?, ?, 'active', ?)",
            (user, auction, amount, created_at),
        )
        self.conn.commit()
        return cur.lastrowid

    def top(self, auction):
        row = highest_bid(self.conn, auction)
        return None if row is None else (row["id"], row["amount"])

    def standing(self, user, bid):
        items = list_my_bids(self.conn, user, limit=100)["items"]
        return next(item["standing"] for item in items if item["id"] == bid)

    def test_cancel_highest_restores_previous_price(self):
        others = place_bid(self.conn, 5, 7, 100, PLACED)
        mine = place_bid(self.conn, 42, 7, 500, PLACED)
        self.assertEqual(cancel_bid(self.conn, mine, 42, PLACED), 7)
        self.assertEqual(minimum_bid(self.conn, 7), {"auction_id": 7, "highest": 100, "step": 10, "minimum_bid": 110})
        self.assertEqual(self.top(7), (others, 100))
        self.assertEqual(self.standing(5, others), "winning")

    def test_cancel_across_step_threshold_uses_new_step(self):
        place_bid(self.conn, 5, 7, 1000, PLACED)
        mine = place_bid(self.conn, 42, 7, 1500, PLACED)
        self.assertEqual(minimum_bid(self.conn, 7)["step"], 50)
        cancel_bid(self.conn, mine, 42, PLACED)
        self.assertEqual(minimum_bid(self.conn, 7), {"auction_id": 7, "highest": 1000, "step": 50, "minimum_bid": 1050})

    def test_cancel_drops_step_back_below_1000(self):
        place_bid(self.conn, 5, 13, 990, PLACED)
        mine = place_bid(self.conn, 42, 13, 1000, PLACED)
        self.assertEqual(minimum_bid(self.conn, 13)["minimum_bid"], 1050)
        cancel_bid(self.conn, mine, 42, PLACED)
        self.assertEqual(minimum_bid(self.conn, 13), {"auction_id": 13, "highest": 990, "step": 10, "minimum_bid": 1000})

    def test_cancel_tied_later_bid_keeps_earlier_highest(self):
        first = self.insert(5, 7, 200, PLACED)
        later = self.insert(42, 7, 200, PLACED + 1)
        self.assertEqual(self.top(7), (first, 200))
        cancel_bid(self.conn, later, 42, PLACED + 1)
        self.assertEqual(self.top(7), (first, 200))
        self.assertEqual(minimum_bid(self.conn, 7)["minimum_bid"], 210)

    def test_cancel_tie_winner_passes_highest_to_other(self):
        mine = self.insert(42, 7, 200, PLACED)
        other = self.insert(5, 7, 200, PLACED + 1)
        self.assertEqual(self.top(7), (mine, 200))
        cancel_bid(self.conn, mine, 42, PLACED + 1)
        self.assertEqual(self.top(7), (other, 200))
        self.assertEqual(self.standing(5, other), "winning")
        self.assertEqual(minimum_bid(self.conn, 7)["minimum_bid"], 210)

    def test_same_amount_as_cancelled_bid_is_accepted(self):
        first = place_bid(self.conn, 42, 7, 500, PLACED)
        cancel_bid(self.conn, first, 42, PLACED)
        again = place_bid(self.conn, 42, 7, 500, PLACED + 1000)
        self.assertEqual(self.top(7), (again, 500))

    def test_all_bids_cancelled_leaves_no_highest(self):
        base = place_bid(self.conn, 5, 7, 100, PLACED)
        mid = place_bid(self.conn, 42, 7, 200, PLACED)
        top = place_bid(self.conn, 42, 7, 300, PLACED)
        cancel_bid(self.conn, top, 42, PLACED)
        self.assertEqual(self.top(7), (mid, 200))
        cancel_bid(self.conn, mid, 42, PLACED)
        self.assertEqual(self.top(7), (base, 100))
        cancel_bid(self.conn, base, 5, PLACED)
        self.assertIsNone(highest_bid(self.conn, 7))
        self.assertEqual(minimum_bid(self.conn, 7), {"auction_id": 7, "highest": None, "step": None, "minimum_bid": 1})


if __name__ == "__main__":
    unittest.main()
