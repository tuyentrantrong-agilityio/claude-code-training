"""T-01 S2, S3: the Cancel column and dialog on the page (intent/2026-11-02-cancel-bid).

The page script runs in Node (tests/js/cancel_harness.js) with a fake DOM and a fake
fetch; skipped where Node is not installed.
"""
import json
import os
import re
import shutil
import subprocess
import unittest

HERE = os.path.dirname(__file__)
INDEX = os.path.join(HERE, "..", "webapp", "index.html")
HARNESS = os.path.join(HERE, "js", "cancel_harness.js")
DIALOG = "Cancel bid 31 on auction 7 (amount 500)? This cannot be undone."


class CancelMarkupTest(unittest.TestCase):
    def test_cancel_notice_sits_directly_above_the_table(self):
        with open(INDEX, encoding="utf-8") as f:
            html = f.read()
        notice = '<p id="cancel-notice" aria-live="polite" style="color:#666"></p>'
        self.assertRegex(html, re.escape(notice) + r"\s*<table>")
        self.assertIn(
            "<th>ID</th><th>Auction</th><th>Amount</th><th>Status</th><th>Standing</th><th>Cancel</th>", html
        )


@unittest.skipUnless(shutil.which("node"), "node is not installed")
class CancelPageTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        out = subprocess.run(["node", HARNESS, INDEX], capture_output=True, text=True, timeout=60)
        if out.returncode != 0:
            raise AssertionError(out.stderr)
        cls.r = json.loads(out.stdout)

    def scenario(self, name):
        result = self.r[name]
        self.assertNotIn("crash", result, result.get("crash"))
        return result

    def test_confirm_accepted_cancels_and_shows_notice(self):
        got = self.scenario("accepted")
        self.assertEqual(got["confirms"], [DIALOG])
        self.assertEqual(got["rowsBefore"], [[31, 7, 500, "active", "Winning", ""]])
        self.assertEqual(got["during"], {"disabled": True, "posts": ["/api/bids/31/cancel"], "notice": ""})
        self.assertEqual(got["posts"], ["/api/bids/31/cancel"])
        self.assertEqual(got["loads"], 2)
        self.assertEqual(got["notice"], "Bid 31 on auction 7 cancelled.")
        self.assertEqual(got["error"], "")
        self.assertEqual(got["rowsAfter"], [[31, 7, 500, "cancelled", "-", ""]])
        self.assertEqual(got["buttonsAfter"], [False])

    def test_cancel_column_button_only_on_active_rows(self):
        got = self.scenario("buttonsPerRow")
        self.assertEqual(
            got["rows"],
            [[31, 7, 500, "active", "Winning", ""], [32, 8, 90, "cancelled", "-", ""], [33, 9, 70, "active", "Outbid", ""]],
        )
        self.assertEqual(got["buttons"], ["Cancel bid", None, "Cancel bid"])

    def test_confirm_dismissed_sends_nothing(self):
        got = self.scenario("dismissed")
        self.assertEqual(got["confirms"], [DIALOG])
        self.assertEqual(got["posts"], [])
        self.assertEqual(got["loads"], 1)
        self.assertEqual(got["disabled"], False)
        self.assertEqual(got["notice"], "")
        self.assertEqual(got["rows"], [[31, 7, 500, "active", "Winning", ""]])
        self.assertEqual(got["hasButton"], [True])


if __name__ == "__main__":
    unittest.main()
