"""T-01 Reject bids below the minimum (intent/2026-11-02-minimum-raise, M-001 to M-012)."""
import json
import threading
import unittest
import urllib.error
import urllib.request

from webapp.server import make_server, place_bid

OTHER, T = 5, 1_700_000_000_000


class MinimumRaiseApiTest(unittest.TestCase):
    def setUp(self):
        self.server = make_server(0)
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()

    def seed(self, auction_id, amount):
        """A bid by another user, stored the way the API would store it."""
        with self.server.db_lock:
            place_bid(self.server.db, OTHER, auction_id, amount, T)

    def call(self, path, body=None):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.base + path, data=data)
        try:
            with urllib.request.urlopen(req) as resp:
                return resp.status, json.loads(resp.read())
        except urllib.error.HTTPError as err:
            return err.code, json.loads(err.read())

    def bid(self, auction_id, amount):
        return self.call("/api/bids", {"auction_id": auction_id, "amount": amount})

    def stored(self):
        return self.server.db.execute("SELECT COUNT(*) FROM bids").fetchone()[0]

    def my_bids(self):
        return self.call("/api/bids?limit=100")[1]["items"]

    def assert_steps(self, auction_id, highest, low, minimum):
        self.seed(auction_id, highest)
        self.assertEqual(self.bid(auction_id, low), (409, {"error": f"bid must be at least {minimum}"}))
        status, _ = self.bid(auction_id, minimum)
        self.assertEqual(status, 201)

    def test_exact_minimum_under_1000_is_accepted(self):
        self.seed(7, 100)
        status, body = self.bid(7, 110)
        self.assertEqual(status, 201)
        self.assertIsInstance(body["id"], int)
        mine = self.my_bids()
        self.assertEqual([(b["auction_id"], b["amount"], b["standing"]) for b in mine], [(7, 110, "winning")])

    def test_below_minimum_is_refused_with_minimum_on_api_and_page(self):
        # API half of M-002; the page half (red line, fields kept) is the browser check.
        self.seed(7, 100)
        self.assertEqual(self.bid(7, 109), (409, {"error": "bid must be at least 110"}))
        self.assertEqual(self.stored(), 1)

    def test_step_10_applies_up_to_highest_999(self):
        self.assert_steps(8, 999, 1008, 1009)

    def test_step_50_applies_from_highest_1000(self):
        self.assert_steps(9, 1000, 1049, 1050)

    def test_first_bid_is_free(self):
        self.assertEqual(self.bid(10, 1)[0], 201)
        self.assertEqual([(b["amount"], b["standing"]) for b in self.my_bids()], [(1, "winning")])

    def test_invalid_amount_is_400_before_minimum_check(self):
        self.seed(7, 100)
        cases = [
            ({"auction_id": 7, "amount": 0}, "auction_id and amount must be positive"),
            ({"auction_id": 7, "amount": 110.5}, "auction_id and amount must be integers"),
            ({"auction_id": 7}, "auction_id and amount must be integers"),
        ]
        for body, error in cases:
            with self.subTest(body=body):
                self.assertEqual(self.call("/api/bids", body), (400, {"error": error}))
        self.assertEqual(self.stored(), 1)

    def test_one_above_minimum_is_accepted(self):
        self.seed(7, 100)
        self.assertEqual(self.bid(7, 111)[0], 201)
        self.assertEqual(self.my_bids()[0]["standing"], "winning")

    def test_equal_to_highest_is_refused(self):
        self.seed(7, 100)
        self.assertEqual(self.bid(7, 100), (409, {"error": "bid must be at least 110"}))
        self.assertEqual(self.stored(), 1)

    def test_tier_is_chosen_by_highest_not_offer(self):
        self.assert_steps(16, 990, 999, 1000)

    def test_minimum_with_highest_one(self):
        self.assert_steps(17, 1, 10, 11)

    def test_first_bid_of_max_amount_is_accepted(self):
        self.assertEqual(self.bid(10, 2**63 - 1)[0], 201)
        self.assertEqual(self.stored(), 1)

    def test_negative_and_too_large_amounts_are_400(self):
        for body in ({"auction_id": 10, "amount": -5},
                     {"auction_id": 10, "amount": 2**63},
                     {"auction_id": 0, "amount": 5}):
            with self.subTest(body=body):
                self.assertEqual(self.call("/api/bids", body)[0], 400)
        self.assertEqual(self.stored(), 0)


if __name__ == "__main__":
    unittest.main()
