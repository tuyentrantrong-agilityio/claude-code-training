"""T-01: POST /api/bids/<id>/cancel (intent/2026-11-02-cancel-bid)."""
import http.client
import json
import threading
import unittest

from webapp.server import USER, make_server, place_bid

OTHER, T = 5, 1_700_000_000_000
NOT_FOUND = (404, {"error": "not found"})
INVALID = (400, {"error": "invalid bid_id"})


class CancelApiTest(unittest.TestCase):
    def setUp(self):
        self.server = make_server(0)
        self.port = self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()

    def seed(self, user, auction_id, amount, status="active"):
        with self.server.db_lock:
            return place_bid(self.server.db, user, auction_id, amount, T, status=status)

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
            [{"id": mine, "auction_id": 7, "amount": 500, "status": "cancelled", "created_at": T, "standing": None}],
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
        for segment in ("abc", "0", "9223372036854775808"):
            with self.subTest(segment=segment):
                self.assertEqual(self.cancel(segment), INVALID)

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


if __name__ == "__main__":
    unittest.main()
