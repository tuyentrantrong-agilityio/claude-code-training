"""T-03 S1, S3, S4: GET /api/auctions/<id>/minimum-bid (intent/2026-11-02-minimum-raise)."""
import http.client
import json
import threading
import unittest

from webapp.server import make_server, place_bid

OTHER, T = 5, 1_700_000_000_000
MAX = 2**63 - 1


class MinimumBidEndpointTest(unittest.TestCase):
    def setUp(self):
        self.server = make_server(0)
        self.port = self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()

    def seed(self, auction_id, amount, status="active"):
        with self.server.db_lock:
            place_bid(self.server.db, OTHER, auction_id, amount, T, status=status)

    def request(self, path, method="GET"):
        # http.client sends the path exactly as written (no normalising or quoting).
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        try:
            conn.request(method, path)
            resp = conn.getresponse()
            return resp.status, json.loads(resp.read())
        finally:
            conn.close()

    def lookup(self, auction_id):
        return self.request(f"/api/auctions/{auction_id}/minimum-bid")

    def test_lookup_returns_minimum_next_bid(self):
        self.seed(7, 1200)
        self.assertEqual(self.lookup(7), (200, {"auction_id": 7, "highest": 1200, "step": 50, "minimum_bid": 1250}))

    def test_lookup_at_999_uses_step_10(self):
        self.seed(8, 999)
        self.assertEqual(self.lookup(8), (200, {"auction_id": 8, "highest": 999, "step": 10, "minimum_bid": 1009}))

    def test_lookup_at_1000_uses_step_50(self):
        self.seed(9, 1000)
        self.assertEqual(self.lookup(9), (200, {"auction_id": 9, "highest": 1000, "step": 50, "minimum_bid": 1050}))

    def test_minimum_above_max_amount_is_exact_integer(self):
        self.seed(10, 9223372036854775800)
        body = {"auction_id": 10, "highest": 9223372036854775800, "step": 50, "minimum_bid": 9223372036854775850}
        self.assertEqual(self.lookup(10), (200, body))

    def test_leading_zeros_and_query_string(self):
        self.seed(7, 1200)
        expected = self.lookup(7)
        self.assertEqual(self.lookup("007"), expected)
        self.assertEqual(self.request("/api/auctions/7/minimum-bid?x=1"), expected)

    def test_lookup_for_auction_without_bids(self):
        self.assertEqual(self.lookup(20), (200, {"auction_id": 20, "highest": None, "step": None, "minimum_bid": 1}))

    def test_lookup_ignores_cancelled_bids(self):
        self.seed(12, 300, status="cancelled")
        self.assertEqual(self.lookup(12), (200, {"auction_id": 12, "highest": None, "step": None, "minimum_bid": 1}))

    def test_non_whole_or_out_of_range_id_is_400(self):
        for segment in ("0", "abc", "", "-1", "%207", "%37", "7.0", "1e3", "+7",
                        "9223372036854775808", "99999999999999999999"):
            with self.subTest(segment=segment):
                self.assertEqual(self.lookup(segment), (400, {"error": "invalid auction_id"}))

    def test_lookup_at_max_auction_id_is_valid(self):
        self.assertEqual(self.lookup(MAX), (200, {"auction_id": MAX, "highest": None, "step": None, "minimum_bid": 1}))

    def test_lookup_at_auction_id_1_is_valid(self):
        self.seed(1, 100)
        self.assertEqual(self.lookup(1)[1]["minimum_bid"], 110)

    def test_other_path_shapes_are_404(self):
        for path in ("/api/auctions/7/minimum-bid/", "/api/auctions/7/8/minimum-bid"):
            with self.subTest(path=path):
                self.assertEqual(self.request(path), (404, {"error": "not found"}))

    def test_methods_other_than_get_are_404(self):
        for method in ("POST", "PUT", "DELETE", "PATCH"):
            with self.subTest(method=method):
                self.assertEqual(self.request("/api/auctions/7/minimum-bid", method), (404, {"error": "not found"}))


if __name__ == "__main__":
    unittest.main()
