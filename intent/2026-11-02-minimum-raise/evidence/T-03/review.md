# Review: origin-feat-t-03-show-minimum-next-bid

## Findings

- [major] day-11/webapp/server.py:67 `if not (segment.isascii() and segment.isdigit() and 1 <= int(segment) <= MAX_VALUE):` calls int() on a digits-only segment of any length. On Python 3.11 and later (CI uses 3.12), int() raises ValueError for a string longer than 4300 digits (the int max str digits limit). The handler does not catch it, so `GET /api/auctions/<5000 digits>/minimum-bid` gets no response at all instead of 400 `{"error": "invalid auction_id"}`. Check the length first (for example, more than 19 digits after leading zeros is out of range) or catch ValueError. No test covers this case. Rule: T-03 S4 (a segment whose value is not 1 to 2^63-1 gets 400)
- [major] day-11/webapp/server.py:76 `do_PUT = do_DELETE = do_PATCH = _not_found` covers only three methods. HEAD and OPTIONS (and any other method) still fall through to BaseHTTPRequestHandler and get a 501 "Unsupported method" HTML page, not 404 `{"error": "not found"}`. test_methods_other_than_get_are_404 only tries POST, PUT, DELETE and PATCH. docs/baseline.md:56 now says "anything else (other paths, other methods) | 404", which is not true for HEAD or OPTIONS. Rule: T-03 S4 (any method other than GET returns 404, no 405)
- [minor] day-11/tests/test_minimum_hint.py:49 `self.assertEqual(self.scenario("noBids")["hint"], "No bids yet: any amount from 1")` is the planned test for M-029. M-029 Expected also says 200 `{"auction_id": 20, "highest": null, "step": null, "minimum_bid": 1}`, but this test only checks the hint against a faked body. The endpoint body is asserted in a different test (test_minimum_bid_endpoint.py::test_lookup_for_auction_without_bids). M-030 has the same gap: test_invalid_auction_id_gives_empty_hint_and_no_request does not assert that `GET /api/auctions/0/minimum-bid` returns 400; test_non_whole_or_out_of_range_id_is_400 does. Either list both tests in the row or split the row. Rule: matrix, planned test asserts the full Expected
- [minor] day-11/tests/test_minimum_bid_endpoint.py:81 `self.assertEqual(self.lookup(1)[1]["minimum_bid"], 110)` drops the status code that M-038 Expected names ("200 `minimum_bid` 110"). Assert `(200, {...})` as the other endpoint tests do. Rule: matrix M-038

## Checked

- T-03 S1 to S6 against day-11/webapp/server.py, day-11/webapp/index.html, day-02/auction/bids.py (minimum_bid, minimum_step, minimum_next_bid, highest_bid) and both new test files: every Then is implemented and tested; no finding beyond the above. Confirmed in the code and tests: the hint is cleared at once on each input and when the POST finishes; stale answers are dropped by hintSeq; the refresh runs after 201, 400, 409, 500 and network failure, using the field value at that moment; neither field is cleared after a bid; the hint comes only from the raw minimum_bid digits, so amounts above 2^53 keep every digit; the hint markup has aria-live and #666; the endpoint answers 007 and ignores the query string; the raw segment is not percent-decoded (%37 gives 400); a trailing slash or an extra segment gives 404.
- T-03 Out of scope: no change to the My bids table, no auto-fill of Amount, no timer refresh, no debounce. Respected.
- Matrix rows M-027 to M-044: every planned test exists (check_matrix 18/18) and asserts the Expected, except the gaps noted for M-029, M-030 and M-038. M-043 and M-044 Expected now state the BA decisions from T-03 Questions instead of "blocked by question".
- Tests: the hint tests run the page's real script in Node via day-11/tests/js/hint_harness.js with no network; the server tests use make_server(0). No existing assertion was weakened. The Node tests skip without node; CI runs on ubuntu-latest, which ships Node.
- Repo checks in context.md: check_branch all PASS, run_tests 175 OK, check_matrix OK.
- Repo rules: stdlib only, plain ASCII in added lines, commit messages in the right format with no AI mention, no generated files. docs/baseline.md is updated for the endpoint and the hint (but see the HEAD/OPTIONS finding). The chore commit to .claude/skills/run-tests/run_tests.py (skipped count in the summary) is tooling only and does not change app behaviour.

## Verified after the review

Produced by the `reviewer` agent through `/review-pr` on PR #9 (base cf8b470, head e208a1a),
saved unchanged. The two major findings and the `;params` path were then reproduced
against a live `make_server(0)`:

- `HEAD /api/auctions/7/minimum-bid` -> 501, `OPTIONS` -> 501 HTML (expected 404 JSON)
- `GET /api/auctions/<5000 digits>/minimum-bid` -> handler raises ValueError, connection
  closed with no response (expected 400 `invalid auction_id`)
- `GET /api/auctions/7/minimum-bid;x` -> 200 (an unknown path shape should be 404)

Fixed in a follow-up `fix/` pull request.
