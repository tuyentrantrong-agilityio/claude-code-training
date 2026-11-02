import json
import threading
import unittest
import urllib.error
import urllib.request

from webapp.server import make_server


class ServerTest(unittest.TestCase):
    def setUp(self):
        self.server = make_server(0)
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()

    def call(self, path, body=None):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.base + path, data=data)
        try:
            with urllib.request.urlopen(req) as resp:
                return resp.status, json.loads(resp.read())
        except urllib.error.HTTPError as err:
            return err.code, json.loads(err.read())

    def test_index_served(self):
        with urllib.request.urlopen(self.base + "/") as resp:
            self.assertIn(b"<form", resp.read())

    def test_place_and_list(self):
        status, _ = self.call("/api/bids", {"auction_id": "7", "amount": "150"})
        self.assertEqual(status, 201)
        status, body = self.call("/api/bids?limit=10")
        self.assertEqual(status, 200)
        self.assertEqual(body["items"][0]["amount"], 150)

    def test_low_bid_rejected_with_409(self):
        self.call("/api/bids", {"auction_id": "7", "amount": "150"})
        status, body = self.call("/api/bids", {"auction_id": "7", "amount": "150"})
        self.assertEqual(status, 409)
        # Minimum raise rule: highest 150 -> at least 160 (was "higher than 150").
        self.assertEqual(body["error"], "bid must be at least 160")

    def test_huge_numbers_rejected_with_400(self):
        status, body = self.call("/api/bids", {"auction_id": "1", "amount": str(2**70)})
        self.assertEqual(status, 400)
        self.assertEqual(body["error"], "auction_id and amount are too large")
        status, _ = self.call("/api/bids", {"auction_id": str(2**63), "amount": "5"})
        self.assertEqual(status, 400)

    def test_non_integer_json_values_rejected(self):
        for amount in (150.9, True, 1e400, "1e400"):
            status, _ = self.call("/api/bids", {"auction_id": 1, "amount": amount})
            self.assertEqual(status, 400, amount)

    def test_bad_cursor_is_400(self):
        status, _ = self.call("/api/bids?cursor=e30=")
        self.assertEqual(status, 400)

    def test_list_includes_standing(self):
        self.call("/api/bids", {"auction_id": "7", "amount": "150"})
        _, body = self.call("/api/bids?limit=10")
        self.assertEqual(body["items"][0]["standing"], "winning")

    def test_pagination_walks_all_bids(self):
        for i in range(1, 6):
            self.call("/api/bids", {"auction_id": i, "amount": 10 * i})
        seen, cursor = [], None
        while True:
            path = "/api/bids?limit=2" + (f"&cursor={cursor}" if cursor else "")
            _, body = self.call(path)
            seen += [b["id"] for b in body["items"]]
            cursor = body["next_cursor"]
            if cursor is None:
                break
        self.assertEqual(sorted(seen), [1, 2, 3, 4, 5])

    def test_invalid_limit_is_400(self):
        for limit in ("0", "101", "abc"):
            status, body = self.call(f"/api/bids?limit={limit}")
            self.assertEqual(status, 400, limit)
            self.assertIn("error", body)

    def test_invalid_bid_is_400(self):
        for payload in ({"auction_id": "x", "amount": 5}, {"auction_id": 1, "amount": -3}, {}):
            status, _ = self.call("/api/bids", payload)
            self.assertEqual(status, 400, payload)


if __name__ == "__main__":
    unittest.main()
