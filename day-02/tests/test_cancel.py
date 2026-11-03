"""T-01: cancel_bid in the bids store (intent/2026-11-02-cancel-bid)."""
import unittest

from auction.bids import BidNotActiveError, BidNotFoundError, cancel_bid, connect, place_bid

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


if __name__ == "__main__":
    unittest.main()
