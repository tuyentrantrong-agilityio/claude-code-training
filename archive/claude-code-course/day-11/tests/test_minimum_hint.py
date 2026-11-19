"""T-03 S2 to S6: the minimum bid hint on the page (intent/2026-11-02-minimum-raise).

The page script runs in Node (tests/js/hint_harness.js) with a fake DOM and a fake
fetch; skipped where Node is not installed. Real rendering is checked in the browser
run (intent/2026-11-02-minimum-raise/evidence/T-03).
"""
import json
import os
import shutil
import subprocess
import unittest

HERE = os.path.dirname(__file__)
INDEX = os.path.join(HERE, "..", "webapp", "index.html")
HARNESS = os.path.join(HERE, "js", "hint_harness.js")
LOOKUP_7 = "/api/auctions/7/minimum-bid"


class HintMarkupTest(unittest.TestCase):
    def setUp(self):
        with open(INDEX, encoding="utf-8") as f:
            self.html = f.read()

    def test_hint_element_sits_under_amount(self):
        tag = '<p id="min-bid-hint" aria-live="polite" style="color:#666"></p>'
        self.assertIn(tag, self.html)
        self.assertLess(self.html.index('id="amount"'), self.html.index(tag))
        self.assertLess(self.html.index(tag), self.html.index('id="place"'))


@unittest.skipUnless(shutil.which("node"), "node is not installed")
class HintBehaviourTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        out = subprocess.run(["node", HARNESS, INDEX], capture_output=True, text=True, timeout=60)
        if out.returncode != 0:
            raise AssertionError(out.stderr)
        cls.r = json.loads(out.stdout)

    def scenario(self, name):
        result = self.r[name]
        self.assertNotIn("crash", result, result.get("crash") if isinstance(result, dict) else None)
        return result

    def test_hint_shows_minimum_for_typed_auction(self):
        self.assertEqual(self.scenario("typed"), {"hint": "Minimum next bid: 110", "lookups": [LOOKUP_7]})

    def test_hint_for_auction_without_bids(self):
        self.assertEqual(self.scenario("noBids")["hint"], "No bids yet: any amount from 1")

    def test_invalid_auction_id_gives_empty_hint_and_no_request(self):
        for value, got in self.scenario("invalid").items():
            with self.subTest(value=value):
                self.assertEqual(got, {"hint": "", "lookups": 0})

    def test_decimal_auction_id_gives_empty_hint(self):
        self.assertEqual(self.scenario("invalid")["7.5"], {"hint": "", "lookups": 0})

    def test_auction_id_with_leading_zeros(self):
        self.assertEqual(self.scenario("trimmed")[" 007 "], {"hint": "Minimum next bid: 110", "lookups": [LOOKUP_7]})

    def test_auction_id_with_surrounding_spaces(self):
        self.assertEqual(self.scenario("trimmed")["\t7\t"], {"hint": "Minimum next bid: 110", "lookups": [LOOKUP_7]})

    def test_max_auction_id_is_looked_up(self):
        got = self.scenario("trimmed")["9223372036854775807"]
        self.assertEqual(got["lookups"], ["/api/auctions/9223372036854775807/minimum-bid"])

    def test_failed_lookup_gives_empty_hint(self):
        self.assertEqual(self.scenario("failedLookup"), {"500": "", "network": ""})

    def test_stale_lookup_answer_is_ignored(self):
        self.assertEqual(self.scenario("stale"), {"hintWhilePending": "", "hint": "Minimum next bid: 1009"})

    def test_clearing_auction_id_clears_hint(self):
        got = self.scenario("cleared")
        self.assertEqual((got["before"], got["after"], got["lookups"]), ("Minimum next bid: 110", "", 1))

    def test_hint_refreshes_after_rejected_bid(self):
        got = self.scenario("rejected")
        self.assertEqual(got["error"], "bid must be at least 130")
        self.assertEqual(got["hint"], "Minimum next bid: 130")
        self.assertEqual(got["lookups"], [LOOKUP_7])
        self.assertEqual(got["hintAtRefresh"], "")  # cleared when the POST finished
        self.assertEqual((got["auctionId"], got["amount"]), ("7", "110"))

    def test_failed_refresh_keeps_error_and_empties_hint(self):
        self.assertEqual(self.scenario("rejectedLookupFails"), {"error": "bid must be at least 130", "hint": ""})

    def test_hint_refreshes_after_accepted_bid(self):
        got = self.scenario("accepted")
        self.assertEqual(got["hint"], "Minimum next bid: 1050")
        self.assertEqual(got["lookups"], [LOOKUP_7, LOOKUP_7])  # page load, then after the POST
        self.assertEqual((got["auctionId"], got["amount"]), ("7", "1000"))

    def test_hint_refreshes_after_any_bid_result(self):
        for result, got in self.scenario("otherResults").items():
            with self.subTest(result=result):
                self.assertEqual(got, {"hint": "Minimum next bid: 110", "lookups": [LOOKUP_7, LOOKUP_7]})

    def test_invalid_id_after_bid_gives_empty_hint_and_no_request(self):
        self.assertEqual(self.scenario("invalidIdAfterBid"), {"hint": "", "lookups": 0})

    def test_hint_requested_on_page_load_with_a_value(self):
        got = self.scenario("onLoad")
        self.assertEqual((got["hint"], got["lookups"], got["emptyLookups"]), ("Minimum next bid: 110", [LOOKUP_7], 0))

    def test_large_minimum_keeps_every_digit(self):
        self.assertEqual(self.scenario("largeAmount")["hint"], "Minimum next bid: 9223372036854775850")


if __name__ == "__main__":
    unittest.main()
