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

    def seed(self, auction_id, amount, user=OTHER, status="active"):
        """A bid by another user, stored the way the API would store it."""
        with self.server.db_lock:
            place_bid(self.server.db, user, auction_id, amount, T, status=status)

    def seed_raw(self, auction_id, amount, user, created_at=T):
        """A row stored before the change: no minimum check at all."""
        with self.server.db_lock:
            self.server.db.execute(
                "INSERT INTO bids (user_id, auction_id, amount, created_at) VALUES (?, ?, ?, ?)",
                (user, auction_id, amount, created_at),
            )
            self.server.db.commit()

    def bids_at_once(self, auction_id, amounts):
        """Post the bids from parallel threads released together; return the statuses."""
        barrier = threading.Barrier(len(amounts), timeout=10)
        results = [None] * len(amounts)

        def post(i):
            barrier.wait()
            results[i] = self.bid(auction_id, amounts[i])

        threads = [threading.Thread(target=post, args=(i,)) for i in range(len(amounts))]
        for t in threads:
            t.start()
        for t in threads:
            t.join(10)
        return results

    def amounts_on(self, auction_id):
        rows = self.server.db.execute(
            "SELECT amount FROM bids WHERE auction_id = ? ORDER BY id", (auction_id,)
        )
        return [r[0] for r in rows]

    def call(self, path, body=None):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.base + path, data=data)
        try:
            with urllib.request.urlopen(req) as resp:
                return resp.status, json.loads(resp.read())
        except urllib.error.HTTPError as err:
            with err:
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

    # T-02 Apply the minimum to every bid (M-014 to M-026)

    def test_raising_own_bid_needs_the_step(self):
        self.seed(7, 100, user=42)
        self.assertEqual(self.bid(7, 105), (409, {"error": "bid must be at least 110"}))
        mine = [(b["auction_id"], b["amount"], b["standing"]) for b in self.my_bids()]
        self.assertEqual(mine, [(7, 100, "winning")])

    def test_cancelled_bid_is_ignored_for_minimum(self):
        self.seed(11, 100)
        self.seed(11, 500, user=6, status="cancelled")
        self.assertEqual(self.bid(11, 110)[0], 201)
        self.assertEqual([(b["amount"], b["standing"]) for b in self.my_bids()], [(110, "winning")])

    def test_all_cancelled_auction_takes_free_bid(self):
        self.seed(12, 300, status="cancelled")
        self.assertEqual(self.bid(12, 1)[0], 201)
        self.assertEqual([(b["amount"], b["standing"]) for b in self.my_bids()], [(1, "winning")])

    def test_old_bids_left_alone_and_next_bid_needs_step(self):
        self.seed_raw(13, 100, OTHER, T)
        self.seed_raw(13, 101, 42, T + 1)
        before = [dict(r) for r in self.server.db.execute("SELECT * FROM bids ORDER BY id")]
        mine = self.my_bids()
        self.assertEqual([(b["amount"], b["standing"]) for b in mine], [(101, "winning")])
        after = [dict(r) for r in self.server.db.execute("SELECT * FROM bids ORDER BY id")]
        self.assertEqual(after, before)
        with self.server.db_lock:
            with self.assertRaises(ValueError) as ctx:
                place_bid(self.server.db, OTHER, 13, 110, T + 2)
            self.assertEqual(str(ctx.exception), "bid must be at least 111")
            place_bid(self.server.db, OTHER, 13, 111, T + 3)
        self.assertEqual(self.amounts_on(13), [100, 101, 111])

    def test_two_equal_simultaneous_bids_store_one(self):
        self.seed(14, 100)
        results = sorted(self.bids_at_once(14, [110, 110]), key=lambda r: r[0])
        self.assertEqual(results[0][0], 201)
        self.assertEqual(results[1], (409, {"error": "bid must be at least 120"}))
        self.assertEqual(self.amounts_on(14), [100, 110])

    def test_minimum_above_max_amount_is_refused(self):
        self.seed(15, 9223372036854775800)
        self.assertEqual(self.bid(15, 2**63 - 1), (409, {"error": "bid must be at least 9223372036854775850"}))
        self.assertEqual(self.amounts_on(15), [9223372036854775800])

    def test_cancelled_bid_does_not_raise_minimum_but_step_holds(self):
        self.seed(11, 100)
        self.seed(11, 500, user=6, status="cancelled")
        self.assertEqual(self.bid(11, 109), (409, {"error": "bid must be at least 110"}))

    def test_all_cancelled_auction_still_validates_amount(self):
        self.seed(12, 300, status="cancelled")
        self.assertEqual(self.bid(12, 0)[0], 400)
        self.assertEqual(self.amounts_on(12), [300])

    def test_tied_highest_amounts_give_one_minimum(self):
        self.seed_raw(18, 100, OTHER, T)
        self.seed_raw(18, 100, 6, T)
        self.assertEqual(self.bid(18, 109), (409, {"error": "bid must be at least 110"}))
        self.assertEqual(self.bid(18, 110)[0], 201)

    def test_simultaneous_different_bids_checked_in_sequence(self):
        for run in range(10):
            with self.subTest(run=run):
                auction_id = 100 + run
                self.seed(auction_id, 100)
                self.bids_at_once(auction_id, [110, 120])
                self.assertIn(self.amounts_on(auction_id), ([100, 110, 120], [100, 120]))

    def test_highest_at_max_amount_refuses_every_bid(self):
        self.seed(19, 2**63 - 1)
        self.assertEqual(self.bid(19, 2**63 - 1), (409, {"error": "bid must be at least 9223372036854775857"}))
        self.assertEqual(self.amounts_on(19), [2**63 - 1])

    def test_repeated_rejected_request_stays_rejected(self):
        self.seed(7, 100)
        for _ in range(2):
            self.assertEqual(self.bid(7, 105), (409, {"error": "bid must be at least 110"}))
        self.assertEqual(self.amounts_on(7), [100])

    def test_repeated_accepted_request_second_is_refused(self):
        self.seed(7, 100)
        self.assertEqual(self.bid(7, 110)[0], 201)
        self.assertEqual(self.bid(7, 110), (409, {"error": "bid must be at least 120"}))


if __name__ == "__main__":
    unittest.main()
