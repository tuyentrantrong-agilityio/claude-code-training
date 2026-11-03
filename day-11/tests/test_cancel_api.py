"""T-01 to T-03: POST /api/bids/<id>/cancel, its 5 minute window and the auction afterwards (intent/2026-11-02-cancel-bid)."""
import http.client
import json
import threading
import time
import unittest

from webapp.server import USER, list_my_bids, make_server, place_bid

OTHER, MINUTE = 5, 60_000
TOO_LATE = (409, {"error": "too late to cancel: bids can only be cancelled within 5 minutes"})
NOT_FOUND = (404, {"error": "not found"})
INVALID = (400, {"error": "invalid bid_id"})


class ApiCase(unittest.TestCase):
    def setUp(self):
        self.server = make_server(0)
        self.port = self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()

    def seed(self, user, auction_id, amount, status="active", age_ms=MINUTE):
        # Rows go straight into the store the server uses, placed age_ms before now.
        placed = int(time.time() * 1000) - age_ms
        with self.server.db_lock:
            return place_bid(self.server.db, user, auction_id, amount, placed, status=status)

    def stored(self):
        with self.server.db_lock:
            rows = self.server.db.execute("SELECT * FROM bids ORDER BY id").fetchall()
        return [dict(r) for r in rows]

    def request(self, method, path, body=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        try:
            conn.request(method, path, body=body)
            resp = conn.getresponse()
            return resp.status, json.loads(resp.read())
        finally:
            conn.close()

    def cancel(self, bid_id):
        return self.request("POST", f"/api/bids/{bid_id}/cancel")


class CancelApiTest(ApiCase):
    def test_cancel_own_active_bid_returns_200_and_stores_cancelled(self):
        self.seed(OTHER, 7, 100)
        mine = self.seed(USER, 7, 500)
        before = self.stored()[1]
        self.assertEqual(self.cancel(mine), (200, {"id": mine, "auction_id": 7, "status": "cancelled"}))
        self.assertEqual(self.stored()[1], {**before, "status": "cancelled"})
        status, page = self.request("GET", "/api/bids")
        self.assertEqual(status, 200)
        self.assertEqual(
            page["items"],
            [{"id": mine, "auction_id": 7, "amount": 500, "status": "cancelled",
              "created_at": before["created_at"], "standing": None}],
        )

    def test_cancel_other_users_or_unknown_bid_is_404(self):
        others = self.seed(OTHER, 7, 100)
        for bid_id in (others, 999):
            with self.subTest(bid_id=bid_id):
                self.assertEqual(self.cancel(bid_id), (404, {"error": "bid not found"}))
        self.assertEqual(self.stored()[0]["status"], "active")

    def test_cancel_already_cancelled_is_409_not_active(self):
        mine = self.seed(USER, 7, 500, status="cancelled")
        before = self.stored()
        self.assertEqual(self.cancel(mine), (409, {"error": "bid is not active"}))
        self.assertEqual(self.stored(), before)

    def test_invalid_bid_id_is_400(self):
        self.seed(USER, 7, 500)
        for segment in ("abc", "0", "9223372036854775808"):
            with self.subTest(segment=segment):
                self.assertEqual(self.cancel(segment), INVALID)
        self.assertEqual(self.stored()[0]["status"], "active")

    def test_malformed_bid_id_variants_are_400(self):
        self.seed(USER, 7, 500)
        for segment in ("-1", "1.5", ""):
            with self.subTest(segment=segment):
                self.assertEqual(self.cancel(segment), INVALID)
        self.assertEqual(self.stored()[0]["status"], "active")

    def test_wrong_method_or_path_shape_is_404(self):
        mine = self.seed(USER, 7, 500)
        cases = [
            ("GET", f"/api/bids/{mine}/cancel"),
            ("POST", f"/api/bids/{mine}/cancel/"),
            ("POST", f"/api/bids/{mine}/cancel;x=1"),
            ("POST", f"/api/bids/{mine}/extra/cancel"),
            ("PUT", f"/api/bids/{mine}/cancel"),
            ("DELETE", f"/api/bids/{mine}/cancel"),
        ]
        for method, path in cases:
            with self.subTest(method=method, path=path):
                self.assertEqual(self.request(method, path), NOT_FOUND)
        self.assertEqual(self.stored()[0]["status"], "active")

    def test_leading_zeros_in_bid_id_accepted(self):
        mine = self.seed(USER, 7, 500)
        self.assertEqual(self.cancel(f"{mine:03d}"), (200, {"id": mine, "auction_id": 7, "status": "cancelled"}))

    def test_max_bid_id_is_valid_but_not_found(self):
        self.assertEqual(self.cancel(2**63 - 1), (404, {"error": "bid not found"}))

    def test_body_and_query_string_ignored(self):
        mine = self.seed(USER, 7, 500)
        got = self.request("POST", f"/api/bids/{mine}/cancel?x=1", body=b"{junk")
        self.assertEqual(got, (200, {"id": mine, "auction_id": 7, "status": "cancelled"}))

    def test_cancel_touches_only_the_target_row(self):
        others = self.seed(OTHER, 7, 100)
        mine = self.seed(USER, 7, 500)
        before = self.stored()
        self.assertEqual(self.cancel(mine)[0], 200)
        after = self.stored()
        self.assertEqual(after[0], before[0])
        self.assertEqual(after[1], {**before[1], "status": "cancelled"})
        self.assertEqual(others, before[0]["id"])
        post = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        try:
            post.request("POST", "/api/bids", body=json.dumps({"auction_id": 8, "amount": 50}))
            resp = post.getresponse()
            self.assertEqual((resp.status, json.loads(resp.read())), (201, {"id": mine + 1}))
        finally:
            post.close()

    def test_cancel_after_window_is_409_too_late(self):
        late = self.seed(USER, 9, 300, age_ms=6 * MINUTE)
        before = self.stored()
        self.assertEqual(self.cancel(late), TOO_LATE)
        self.assertEqual(self.stored(), before)

    def test_pre_feature_bids_follow_the_same_window(self):
        recent = self.seed(USER, 10, 150, age_ms=2 * MINUTE)
        old = self.seed(USER, 10, 160, age_ms=60 * MINUTE)
        self.assertEqual(self.cancel(recent), (200, {"id": recent, "auction_id": 10, "status": "cancelled"}))
        self.assertEqual(self.cancel(old), TOO_LATE)
        self.assertEqual([row["status"] for row in self.stored()], ["cancelled", "active"])

    def test_two_simultaneous_cancels_one_wins(self):
        mine = self.seed(USER, 11, 120)
        barrier = threading.Barrier(2, timeout=10)
        answers = []

        def worker():
            barrier.wait()
            answers.append(self.cancel(mine))

        threads = [threading.Thread(target=worker) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=20)
        self.assertEqual(
            sorted(answers, key=lambda a: a[0]),
            [(200, {"id": mine, "auction_id": 11, "status": "cancelled"}), (409, {"error": "bid is not active"})],
        )
        self.assertEqual([(row["id"], row["status"]) for row in self.stored()], [(mine, "cancelled")])

    def test_repeated_cancel_second_is_not_active(self):
        mine = self.seed(USER, 11, 120)
        self.assertEqual(self.cancel(mine), (200, {"id": mine, "auction_id": 11, "status": "cancelled"}))
        self.assertEqual(self.cancel(mine), (409, {"error": "bid is not active"}))

    def test_no_limit_on_number_of_cancels(self):
        bids = [self.seed(USER, auction, 100 + auction) for auction in (12, 13, 14)]
        for bid, auction in zip(bids, (12, 13, 14)):
            with self.subTest(bid=bid):
                self.assertEqual(self.cancel(bid), (200, {"id": bid, "auction_id": auction, "status": "cancelled"}))
        self.assertEqual([row["status"] for row in self.stored()], ["cancelled"] * 3)


class RecalculationApiTest(ApiCase):
    """T-03: the auction is read again from the remaining active bids after a cancel."""

    def lookup(self, auction_id):
        return self.request("GET", f"/api/auctions/{auction_id}/minimum-bid")

    def bid(self, auction_id, amount):
        return self.request("POST", "/api/bids", body=json.dumps({"auction_id": auction_id, "amount": amount}))

    def my_bids(self):
        status, page = self.request("GET", "/api/bids?limit=100")
        self.assertEqual(status, 200)
        return [(b["id"], b["status"], b["standing"]) for b in page["items"]]

    def standing_of(self, user, bid_id):
        with self.server.db_lock:
            items = list_my_bids(self.server.db, user, limit=100)["items"]
        return next(item["standing"] for item in items if item["id"] == bid_id)

    def test_cancel_outbid_bid_leaves_price_unchanged(self):
        mine = self.seed(USER, 8, 100)
        others = self.seed(OTHER, 8, 200)
        self.assertEqual(self.cancel(mine), (200, {"id": mine, "auction_id": 8, "status": "cancelled"}))
        self.assertEqual(self.lookup(8), (200, {"auction_id": 8, "highest": 200, "step": 10, "minimum_bid": 210}))
        self.assertEqual(self.standing_of(OTHER, others), "winning")

    def test_own_earlier_bid_becomes_winning_again(self):
        earlier = self.seed(USER, 9, 100)
        later = self.seed(USER, 9, 150)
        self.assertEqual(self.my_bids(), [(later, "active", "winning"), (earlier, "active", "outbid")])
        self.assertEqual(self.cancel(later)[0], 200)
        self.assertEqual(self.my_bids(), [(later, "cancelled", None), (earlier, "active", "winning")])
        self.assertEqual(self.lookup(9), (200, {"auction_id": 9, "highest": 100, "step": 10, "minimum_bid": 110}))

    def test_bid_again_after_cancel_is_accepted(self):
        self.seed(OTHER, 7, 100)
        cancelled = self.seed(USER, 7, 500)
        self.cancel(cancelled)
        self.assertEqual(self.bid(7, 150), (201, {"id": cancelled + 1}))
        self.assertEqual(self.bid(7, 500), (201, {"id": cancelled + 2}))
        self.assertEqual(
            self.my_bids(),
            [(cancelled + 2, "active", "winning"), (cancelled + 1, "active", "outbid"), (cancelled, "cancelled", None)],
        )

    def test_cancel_only_bid_frees_the_auction(self):
        mine = self.seed(USER, 12, 300)
        self.cancel(mine)
        self.assertEqual(self.lookup(12), (200, {"auction_id": 12, "highest": None, "step": None, "minimum_bid": 1}))
        # The API has one fixed user (42), so the bid of 1 comes from user 42, not user 5.
        self.assertEqual(self.bid(12, 1), (201, {"id": mine + 1}))
        self.assertEqual(self.lookup(12), (200, {"auction_id": 12, "highest": 1, "step": 10, "minimum_bid": 11}))

    def test_bid_below_new_minimum_after_cancel_is_409(self):
        self.seed(OTHER, 7, 100)
        self.cancel(self.seed(USER, 7, 500))
        before = self.stored()
        self.assertEqual(self.bid(7, 105), (409, {"error": "bid must be at least 110"}))
        self.assertEqual(self.stored(), before)

    def test_minimum_boundary_after_cancel(self):
        self.seed(OTHER, 7, 100)
        cancelled = self.seed(USER, 7, 500)
        self.cancel(cancelled)
        self.assertEqual(self.bid(7, 109), (409, {"error": "bid must be at least 110"}))
        self.assertEqual(self.bid(7, 110), (201, {"id": cancelled + 1}))

    def test_cancel_to_lower_step_refuses_995(self):
        self.seed(OTHER, 13, 990)
        mine = self.seed(USER, 13, 1000)
        self.cancel(mine)
        self.assertEqual(self.lookup(13), (200, {"auction_id": 13, "highest": 990, "step": 10, "minimum_bid": 1000}))
        before = self.stored()
        self.assertEqual(self.bid(13, 995), (409, {"error": "bid must be at least 1000"}))
        self.assertEqual(self.stored(), before)

    def test_cancelled_bid_keeps_place_in_my_bids(self):
        self.seed(OTHER, 7, 100)
        older = self.seed(USER, 7, 500, age_ms=2 * MINUTE)
        newer = self.seed(USER, 8, 300, age_ms=MINUTE)
        before = self.stored()
        self.cancel(older)
        self.assertEqual(self.my_bids(), [(newer, "active", "winning"), (older, "cancelled", None)])
        self.assertEqual([row["id"] for row in self.stored()], [row["id"] for row in before])


if __name__ == "__main__":
    unittest.main()
