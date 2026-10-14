"""Run from day-02/: python -m unittest discover -s tests -t . -v"""

import unittest

from auction.bids import connect, list_my_bids, place_bid

USER = 42
T = 1_760_000_000_000


def fetch_all(conn, limit):
    ids, cursor = [], None
    while True:
        resp = list_my_bids(conn, USER, limit=limit, cursor=cursor)
        ids += [b["id"] for b in resp["items"]]
        cursor = resp["next_cursor"]
        if cursor is None:
            return ids


class CursorPaginationTest(unittest.TestCase):
    def test_distinct_timestamps_returns_every_bid(self):
        conn = connect()
        expected = [place_bid(conn, USER, i, 100, created_at=T + i) for i in range(5)]
        self.assertCountEqual(fetch_all(conn, limit=2), expected)

    def test_same_millisecond_bids_are_not_skipped(self):
        # BUG: bids sharing created_at with the last row of a page are dropped,
        # because the cursor only keeps created_at and the next page uses "<".
        conn = connect()
        place_bid(conn, USER, 1, 100, created_at=T)
        same_ms = [place_bid(conn, USER, a, 200, created_at=T + 5) for a in (2, 3, 4)]
        place_bid(conn, USER, 5, 300, created_at=T + 10)

        ids = fetch_all(conn, limit=2)

        self.assertEqual(len(ids), 5, f"got {ids}")
        for bid_id in same_ms:
            self.assertIn(bid_id, ids)

    def test_no_duplicates_across_pages(self):
        conn = connect()
        for a in range(6):
            place_bid(conn, USER, a, 100, created_at=T)
        ids = fetch_all(conn, limit=4)
        self.assertEqual(len(ids), len(set(ids)))

    def test_many_same_millisecond_bids_across_pages(self):
        conn = connect()
        expected = []
        for a in range(4):
            expected.append(place_bid(conn, USER, a, 100, created_at=T))

        ids = fetch_all(conn, limit=2)
        self.assertCountEqual(ids, expected)


if __name__ == "__main__":
    unittest.main()
