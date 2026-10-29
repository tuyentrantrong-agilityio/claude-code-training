import unittest

from auction.bids import BidTooLowError, connect, list_my_bids, place_bid

ME, OTHER, T = 42, 5, 1_700_000_000_000


def standings(conn, **kw):
    return {i["id"]: i["standing"] for i in list_my_bids(conn, ME, **kw)["items"]}


class StandingTest(unittest.TestCase):
    def setUp(self):
        self.conn = connect()

    def test_single_bid_is_winning(self):
        bid = place_bid(self.conn, ME, 7, 100, T)
        self.assertEqual(standings(self.conn), {bid: "winning"})

    def test_beaten_bid_is_outbid(self):
        bid = place_bid(self.conn, ME, 7, 100, T)
        place_bid(self.conn, OTHER, 7, 150, T + 1)
        self.assertEqual(standings(self.conn), {bid: "outbid"})

    def test_equal_amount_earlier_wins(self):
        # inserted directly: place_bid refuses equal amounts
        mine = self.conn.execute(
            "INSERT INTO bids (user_id, auction_id, amount, created_at) VALUES (?, 7, 100, ?)",
            (ME, T),
        ).lastrowid
        self.conn.execute(
            "INSERT INTO bids (user_id, auction_id, amount, created_at) VALUES (?, 7, 100, ?)",
            (OTHER, T + 1),
        )
        self.assertEqual(standings(self.conn), {mine: "winning"})

    def test_own_lower_bid_is_outbid(self):
        low = place_bid(self.conn, ME, 7, 100, T)
        high = place_bid(self.conn, ME, 7, 120, T + 1)
        self.assertEqual(standings(self.conn), {low: "outbid", high: "winning"})

    def test_standing_uses_whole_auction_not_page(self):
        top = place_bid(self.conn, ME, 7, 200, T)
        other_auction = place_bid(self.conn, ME, 8, 50, T + 1)
        got = standings(self.conn, limit=1)
        self.assertEqual(got, {other_auction: "winning"})
        cursor = list_my_bids(self.conn, ME, 1)["next_cursor"]
        self.assertEqual(standings(self.conn, limit=1, cursor=cursor), {top: "winning"})

    def test_inactive_bid_is_ignored_for_top(self):
        place_bid(self.conn, OTHER, 7, 500, T, status="cancelled")
        bid = place_bid(self.conn, ME, 7, 100, T + 1)
        self.assertEqual(standings(self.conn), {bid: "winning"})

    def test_own_inactive_bid_has_no_standing(self):
        bid = place_bid(self.conn, ME, 7, 100, T, status="cancelled")
        self.assertEqual(standings(self.conn), {bid: None})


class RejectLowBidTest(unittest.TestCase):
    def setUp(self):
        self.conn = connect()
        place_bid(self.conn, OTHER, 7, 150, T)

    def count(self):
        return self.conn.execute("SELECT COUNT(*) FROM bids").fetchone()[0]

    def test_lower_and_equal_rejected(self):
        for amount in (100, 150):
            with self.assertRaises(BidTooLowError) as ctx:
                place_bid(self.conn, ME, 7, amount, T + 1)
            self.assertEqual(str(ctx.exception), "bid must be higher than 150")
        self.assertEqual(self.count(), 1)

    def test_just_above_accepted(self):
        place_bid(self.conn, ME, 7, 151, T + 1)
        self.assertEqual(self.count(), 2)

    def test_first_bid_any_amount(self):
        place_bid(self.conn, ME, 9, 1, T)
        self.assertEqual(self.count(), 2)

    def test_self_outbid_allowed(self):
        place_bid(self.conn, ME, 8, 10, T)
        place_bid(self.conn, ME, 8, 11, T + 1)
        self.assertEqual(self.count(), 3)


if __name__ == "__main__":
    unittest.main()
