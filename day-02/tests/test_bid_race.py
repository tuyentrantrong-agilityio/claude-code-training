import os
import tempfile
import threading
import unittest

from auction.bids import BidTooLowError, connect, place_bid

T = 1_700_000_000_000


class ConcurrentBidTest(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        connect(self.path).close()

    def tearDown(self):
        os.remove(self.path)

    def test_equal_bids_at_once_store_only_one(self):
        results = []
        barrier = threading.Barrier(20)

        def bid(user_id):
            conn = connect(self.path)
            barrier.wait()
            try:
                place_bid(conn, user_id, 7, 100, T)
                results.append("ok")
            except BidTooLowError:
                results.append("rejected")
            finally:
                conn.close()

        threads = [threading.Thread(target=bid, args=(u,)) for u in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(results.count("ok"), 1)
        self.assertEqual(results.count("rejected"), 19)
        conn = connect(self.path)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM bids").fetchone()[0], 1)
        conn.close()


if __name__ == "__main__":
    unittest.main()
