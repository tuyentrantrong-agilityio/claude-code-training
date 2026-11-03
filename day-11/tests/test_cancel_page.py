"""T-01, T-02 and T-04: the Cancel column, dialog, notice and what the page does after a cancel (intent/2026-11-02-cancel-bid).

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

    def test_not_active_answer_reloads_then_shows_error(self):
        got = self.scenario("notActive")
        self.assertEqual(got["posts"], ["/api/bids/31/cancel"])
        self.assertEqual(got["loads"], 2)
        self.assertEqual(got["notice"], "")
        self.assertEqual(got["error"], "bid is not active")
        self.assertEqual(got["rows"], [[31, 7, 500, "cancelled", "-", ""]])
        self.assertEqual(got["hasButton"], [False])
        self.assertEqual(got["hint"], "Minimum next bid: 110")
        self.assertEqual(got["lookups"], ["/api/auctions/7/minimum-bid"])
        self.assertEqual(got["stored"], {"7": "winning"})

    def test_not_found_answer_reloads_then_shows_error(self):
        got = self.scenario("notFound")
        self.assertEqual(got["posts"], ["/api/bids/31/cancel"])
        self.assertEqual(got["loads"], 2)
        self.assertEqual(got["notice"], "")
        self.assertEqual(got["error"], "bid not found")
        self.assertEqual(got["rows"], [[31, 7, 500, "active", "Winning", ""]])
        self.assertEqual(got["hint"], "Minimum next bid: 510")
        self.assertEqual(got["lookups"], ["/api/auctions/7/minimum-bid"])
        self.assertEqual(got["stored"], {"7": "winning"})

    def test_network_failure_shows_could_not_cancel(self):
        got = self.scenario("networkFailure")
        self.assertEqual(got["posts"], ["/api/bids/31/cancel"])
        self.assertEqual(got["loads"], 1)
        self.assertEqual(got["disabled"], False)
        self.assertEqual(got["notice"], "")
        self.assertEqual(got["error"], "could not cancel bid 31")
        self.assertEqual(got["rows"], [[31, 7, 500, "active", "Winning", ""]])
        self.assertEqual((got["hintBefore"], got["hintAfter"], got["lookups"]), ("Minimum next bid: 510", "Minimum next bid: 510", []))

    def test_other_status_shows_could_not_cancel(self):
        for name, got in self.scenario("otherStatus").items():
            with self.subTest(answer=name):
                self.assertEqual(
                    got,
                    {"posts": ["/api/bids/31/cancel"], "loads": 1, "disabled": False, "notice": "",
                     "error": "could not cancel bid 31", "rows": [[31, 7, 500, "active", "Winning", ""]],
                     "lookups": [], "stored": {"7": "winning"}},
                )

    def test_notice_cleared_by_next_cancel_or_bid_post(self):
        self.assertEqual(
            self.scenario("noticeCleared"),
            {"afterFirst": "Bid 31 on auction 7 cancelled.",
             "duringSecond": {"notice": "", "error": ""},
             "afterSecond": "Bid 32 on auction 8 cancelled.",
             "afterBidPost": ""},
        )

    def test_too_late_shows_error_line_and_keeps_button(self):
        got = self.scenario("tooLate")
        self.assertEqual(got["posts"], ["/api/bids/42/cancel"])
        self.assertEqual(got["loads"], 2)
        self.assertEqual(got["notice"], "")
        self.assertEqual(got["error"], "too late to cancel: bids can only be cancelled within 5 minutes")
        self.assertEqual(got["rows"], [[42, 9, 300, "active", "Winning", ""]])
        self.assertEqual(got["hasButton"], [True])
        self.assertEqual(got["disabled"], [False])

    def test_button_shown_on_old_active_rows(self):
        self.assertEqual(self.scenario("oldActiveRows"), {"buttons": ["Cancel bid", "Cancel bid"]})

    def test_cancel_reloads_first_page_with_page_size(self):
        got = self.scenario("reloadsFirstPage")
        self.assertEqual(got["rowsBefore"], [61, 60, 50, 40])
        self.assertEqual(got["lists"], ["/api/bids?limit=2"])
        self.assertEqual(
            got["rowsAfter"],
            [[61, 9, 150, "cancelled", "-", ""], [60, 9, 100, "active", "Winning", ""]],
        )

    def test_hint_refreshes_and_form_keeps_values(self):
        self.assertEqual(
            self.scenario("hintRefreshes"),
            {"hintBefore": "Minimum next bid: 510", "hintAfter": "Minimum next bid: 110", "auctionId": "7", "amount": "120"},
        )

    def test_hint_empty_for_invalid_auction_id_after_cancel(self):
        self.assertEqual(self.scenario("hintInvalidId"), {"hint": "", "lookups": []})

    def test_hint_uses_current_auction_id_field(self):
        self.assertEqual(self.scenario("hintCurrentField"), {"lookups": ["/api/auctions/8/minimum-bid"]})

    def test_cancel_never_shows_outbid_banner(self):
        self.assertEqual(
            self.scenario("neverShowsBanner"),
            {"bannerBefore": "",
             "afterCancel": {"banner": "",
                             "rows": [[82, 20, 120, "cancelled", "-", ""], [80, 20, 100, "active", "Outbid", ""]],
                             "stored": {"20": "outbid"}},
             "afterBrowserReload": ""},
        )

    def test_cancel_forgets_the_stored_standing_of_the_auction(self):
        self.assertEqual(
            self.scenario("standingForgotten"),
            {"before": {"20": "winning", "21": "winning"}, "after": {"21": "winning"}, "banner": ""},
        )

    def test_real_outbid_still_shows_banner_after_cancel(self):
        self.assertEqual(self.scenario("realOutbid"), {"banner": "You were outbid on auction 21"})

    def test_reload_failure_still_shows_error_and_refreshes_hint(self):
        self.assertEqual(
            self.scenario("reloadFails"),
            {"notice": "", "error": "bid is not active", "hint": "Minimum next bid: 110", "banner": "",
             "stored": {"7": "winning"}},
        )

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
