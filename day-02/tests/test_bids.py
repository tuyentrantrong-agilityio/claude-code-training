import unittest

from auction.bids import BidTooLowError, connect, minimum_next_bid, place_bid

ME, OTHER, T = 42, 5, 1_700_000_000_000


class MinimumNextBidTest(unittest.TestCase):
    def test_step_is_chosen_by_highest(self):
        cases = [(None, 1), (1, 11), (100, 110), (990, 1000), (999, 1009), (1000, 1050), (2500, 2550)]
        for highest, minimum in cases:
            with self.subTest(highest=highest):
                self.assertEqual(minimum_next_bid(highest), minimum)


class PlaceBidMinimumTest(unittest.TestCase):
    def setUp(self):
        self.conn = connect()

    def count(self):
        return self.conn.execute("SELECT COUNT(*) FROM bids").fetchone()[0]

    def test_place_bid_below_minimum_raises_with_minimum(self):
        place_bid(self.conn, OTHER, 7, 100, T)
        with self.assertRaises(BidTooLowError) as ctx:
            place_bid(self.conn, ME, 7, 109, T + 1)
        self.assertEqual(str(ctx.exception), "bid must be at least 110")
        self.assertEqual(ctx.exception.minimum, 110)
        self.assertEqual(self.count(), 1)

    def test_tier_boundaries_in_the_store(self):
        cases = [(999, 1008, 1009), (1000, 1049, 1050), (990, 999, 1000)]
        for auction_id, (highest, low, minimum) in enumerate(cases, start=1):
            with self.subTest(highest=highest):
                place_bid(self.conn, OTHER, auction_id, highest, T)
                with self.assertRaises(BidTooLowError) as ctx:
                    place_bid(self.conn, ME, auction_id, low, T + 1)
                self.assertEqual(str(ctx.exception), f"bid must be at least {minimum}")
                place_bid(self.conn, ME, auction_id, minimum, T + 2)

    def test_max_amount_first_bid_is_stored(self):
        place_bid(self.conn, ME, 10, 2**63 - 1, T)
        self.assertEqual(self.count(), 1)


if __name__ == "__main__":
    unittest.main()
