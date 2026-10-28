import threading
import unittest
import urllib.request

from webapp.server import make_server


class IndexHtmlTest(unittest.TestCase):
    """Markup checks only; JS behaviour needs a browser."""

    @classmethod
    def setUpClass(cls):
        cls.server = make_server(0)
        port = cls.server.server_address[1]
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/") as resp:
            cls.html = resp.read().decode()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def test_standing_column_header(self):
        self.assertIn("<th>Standing</th>", self.html)

    def test_standing_labels(self):
        self.assertIn('"Winning"', self.html)
        self.assertIn('"Outbid"', self.html)

    def test_outbid_banner_element(self):
        self.assertIn('id="outbid-banner"', self.html)
        self.assertIn('role="status"', self.html)

    def test_load_more_hidden_by_default(self):
        self.assertIn('id="more" hidden', self.html)


if __name__ == "__main__":
    unittest.main()
