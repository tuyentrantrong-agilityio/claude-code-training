# T-03 Show the minimum next bid

Status: ready
Issue: #5
Dev rounds: 2
Spec: [Minimum raise](../spec.md#minimum-bid-hint)

## Story

As a bidder
I want the bid form to show the minimum next bid for the auction I typed
So that I can offer enough on the first try

## Scenarios

### S1 Lookup endpoint returns the minimum next bid

Given auction 7 has a highest bid of 1200 by user 5
And auction 8 has a highest bid of 999, auction 9 a highest bid of 1000, auction 10 a highest bid of 9223372036854775800
When the client calls `GET /api/auctions/7/minimum-bid`
Then the API returns 200 `{"auction_id": 7, "highest": 1200, "step": 50, "minimum_bid": 1250}`
And `GET /api/auctions/8/minimum-bid` returns 200 `{"auction_id": 8, "highest": 999, "step": 10, "minimum_bid": 1009}` (`step` is the tier chosen by `highest`)
And `GET /api/auctions/9/minimum-bid` returns 200 `{"auction_id": 9, "highest": 1000, "step": 50, "minimum_bid": 1050}`
And `GET /api/auctions/10/minimum-bid` returns 200 `{"auction_id": 10, "highest": 9223372036854775800, "step": 50, "minimum_bid": 9223372036854775850}` (`minimum_bid` is the exact JSON integer H + step, even above 2^63-1)
And `GET /api/auctions/007/minimum-bid` returns the same 200 body as `/api/auctions/7/minimum-bid`, with `"auction_id": 7`
And `GET /api/auctions/7/minimum-bid?x=1` returns the same 200 body (the query string is ignored)

### S2 Hint shows the minimum when an auction id is typed

Given auction 7 has a highest bid of 100 by user 5
When user 42 types 7 in the Auction ID field of the page
Then the element `id="min-bid-hint"` under the Amount field reads "Minimum next bid: 110"
And the lookup runs on every `input` event of the Auction ID field (each keystroke, paste or clear), and once when the page loads with a value already in the field
And on each `input` event the hint is cleared at once and stays empty until the answer for the value now in the field arrives; answers for an older value are dropped
And the hint text comes only from the `minimum_bid` of the lookup response (no client-side computation), written as plain digits with no thousands separator (1250, not 1,250)
And the hint element has `aria-live="polite"`, grey text colour `#666` and the normal font size

### S3 Auction with no active bid

Given auction 20 has never had a bid
And auction 21 has only one bid, of 500 by user 5, with status `cancelled`
When user 42 types 20 in the Auction ID field
Then `GET /api/auctions/20/minimum-bid` returns 200 `{"auction_id": 20, "highest": null, "step": null, "minimum_bid": 1}`
And the hint line reads "No bids yet: any amount from 1"
And `GET /api/auctions/21/minimum-bid` returns 200 `{"auction_id": 21, "highest": null, "step": null, "minimum_bid": 1}` and typing 21 shows the same hint

### S4 Invalid auction id

Given the bid form is on the page
When user 42 clears the Auction ID field, or types 0, abc, 1e3, +7, 7.0, -5 or 9223372036854775808
Then the hint line is empty and no lookup request is sent
And the page rule is: remove leading and trailing whitespace as JavaScript `String.prototype.trim()` does (spaces, tabs and other whitespace, so "\t7\t" -> auction 7); the rest must be one or more digits 0-9 whose value is 1 to 9223372036854775807 (2^63-1); a valid value is sent with leading zeros removed (" 007 " -> `GET /api/auctions/7/minimum-bid`, hint as for auction 7)
And the endpoint rule is: any path `/api/auctions/<segment>/minimum-bid` with exactly one segment (no `/` inside) is checked; a segment that is not only digits 0-9, or whose value is not 1 to 2^63-1, gets 400 `{"error": "invalid auction_id"}`
And so `/api/auctions/0/minimum-bid`, `/api/auctions/abc/minimum-bid`, `/api/auctions//minimum-bid` (empty segment), `/api/auctions/-1/minimum-bid`, `/api/auctions/%207/minimum-bid` and `/api/auctions/99999999999999999999/minimum-bid` each return 400 `{"error": "invalid auction_id"}`
And the segment is checked as received, without percent-decoding, so any `%` makes it invalid: `/api/auctions/%37/minimum-bid` returns 400 `{"error": "invalid auction_id"}`
And `/api/auctions/7/minimum-bid/` (trailing slash) and `/api/auctions/7/8/minimum-bid` return 404 `{"error": "not found"}`, as any other unknown path
And any method other than GET on `/api/auctions/7/minimum-bid` (for example POST, PUT or DELETE) returns 404 `{"error": "not found"}`, as the baseline "anything else" row (no 405)

### S5 Hint refreshes after a rejected bid

Given auction 7 has a highest bid of 100 and the hint reads "Minimum next bid: 110"
And user 5 then bids 120 on auction 7 through the API
When user 42 bids 110 on auction 7 from the page
Then the red error line reads "bid must be at least 130"
And the page sends a new `GET /api/auctions/7/minimum-bid` and the hint line reads "Minimum next bid: 130" from that response (not from the 409 message)
And the Amount field still shows 110 and the Auction ID field still shows 7
And if that lookup fails (non-200 or network error) the hint line is empty and the red error line still reads "bid must be at least 130"
And the same refresh runs after every bid attempt once its POST has finished, whatever the result (201, 400, 409, other status or network failure), using the Auction ID field value at that moment, with the S4 page rule (an invalid value gives an empty hint and no request)
And when the POST finishes the hint is cleared at once and stays empty until the refresh answer arrives, as on an `input` event in S2 (the old "Minimum next bid: 110" is not kept while the refresh is in flight)
And a bid attempt means a `POST /api/bids` that was actually sent; if the page sends no POST, there is no refresh and the hint is left as it was

### S6 Hint refreshes after an accepted bid

Given auction 7 has a highest bid of 990 and the hint reads "Minimum next bid: 1000"
When user 42 bids 1000 on auction 7 from the page and the API returns 201
Then the page sends a new `GET /api/auctions/7/minimum-bid` and the hint line reads "Minimum next bid: 1050"
And the Auction ID field still shows 7 and the Amount field still shows 1000 (neither field is cleared)

## Out of scope

- Showing the minimum next bid in the My bids table.
- Filling the Amount field with the minimum automatically.
- Refreshing the hint on a timer or when another bidder bids (only on Auction ID change, page load and after a bid attempt).
- Exact display of amounts above 2^53 in the browser.
- Debouncing or rate limiting the lookup requests.

## Questions

- [B] (qa, iter 0) What does the hint show and what does `GET /api/auctions/<id>/minimum-bid` return when the Auction ID is typed with leading zeros (007) or surrounding spaces (" 7 ")? -> BA decision: the page trims spaces and drops leading zeros (" 007 " -> lookup of auction 7, hint as for 7); the endpoint accepts leading zeros (007 -> auction 7) but not spaces (400), because the bidder means auction 7 and one digits-only rule is simplest to test.
- [B] (dev, iter 1) S4/S1: for the page, is a typed value like "1e3", "+7", "7.0", "-5" or a value above 2^63-1 treated as "not a whole number from 1 to 2^63-1" (empty hint, no request)? The leading-zero and spaces case is already an open question, so the rule should be written as one sentence for the page and the endpoint. -> answered in ticket body (iter 1)
- [B] (dev, iter 1) S4: for the endpoint, which path segments get 400 `{"error": "invalid auction_id"}` and which get 404 `{"error": "not found"}`? Examples are `/api/auctions/abc/minimum-bid`, `/api/auctions//minimum-bid`, `/api/auctions/-1/minimum-bid`, `/api/auctions/99999999999999999999/minimum-bid` (above 2^63-1), a trailing slash, and a query string such as `?x=1`. -> BA decision: any single segment (empty included) is validated and gets 400 when invalid; a trailing slash or extra segment is 404; the query string is ignored, because only the path shape decides the route and the segment check decides the id.
- [B] (dev, iter 1) S5: after a rejected bid, is the hint refreshed from a new lookup request (so the 130 comes from the server), or from the amount in the 409 message? What shows if that lookup fails (empty hint, or keep the old one), and does the red error line stay either way? -> answered in ticket body (iter 1)
- [B] (dev, iter 1) S5/S6: which Auction ID value is used for the refresh after a bid attempt? Examples are a bid that is refused with 400 (empty or invalid amount, invalid auction id), a network failure, and the field edited while the POST is in flight. Is the hint refreshed after those attempts too, or only after a 201 or 409? -> BA decision: after every attempt, whatever the result, using the field value when the POST finishes, because the spec says every attempt and the field value is what the bidder sees.
- [B] (dev, iter 1) S6: after an accepted bid, does the Amount field keep its value (as in S5) or is it cleared, as the baseline form may do today? Should the new `GET /api/auctions/<id>/minimum-bid` response be the only thing that sets the hint (not a client-side computation)? -> BA decision: both fields keep their values after 201 and the hint comes only from the lookup response, because it matches the client answer for rejected bids (Q10) and keeps the server the only source of the minimum.
- [N] (dev, iter 1) S1: for H=999 the response is `{"highest": 999, "step": 10, "minimum_bid": 1009}`, and for H=1000 it is step 50. Please confirm that `step` is the tier chosen by H, as in the spec table. -> answered in ticket body (iter 1)
- [N] (dev, iter 1) S1: for an auction whose bids are all cancelled, does the response match S3 (`highest` null, `step` null, `minimum_bid` 1)? Please confirm. -> answered in ticket body (iter 1)
- [N] (dev, iter 1) S1: when H + step is above 2^63-1 (H 9223372036854775800), what does the endpoint return? The spec says POST gets a 409 naming H + step. I assume `minimum_bid` is the unbounded integer H + step with status 200, but this is not stated. -> BA decision: 200 with `minimum_bid` the exact integer H + step, because it matches the number the 409 names (D7).
- [N] (dev, iter 1) S2: what is the hint text while a lookup is in flight, or when the id changes from a valid value to an invalid one (the old hint is cleared)? Is the old hint cleared immediately when the field changes, or kept until the new answer arrives? -> BA decision: cleared immediately on every change and empty until the matching answer arrives, because a stale minimum for another auction would mislead.
- [N] (dev, iter 1) S2: is a lookup sent on every keystroke (the `input` event) or only on `change`/blur? The spec says "every change", and the test would depend on which event is wired. -> BA decision: the `input` event, because the hint should appear as soon as the number is typed.
- [N] (dev, iter 1) S2: what is the hint line's element id or class, so tests and the DOM check can find it? Also, is its colour a specific grey value, and does it need an aria-live attribute? -> BA decision: `id="min-bid-hint"`, colour `#666`, `aria-live="polite"`, because tests need a stable id and screen readers should hear the update.
- [N] (dev, iter 1) S2: is the hint requested when the page first loads with an Auction ID value already in the field (for example one the browser restores)? -> BA decision: yes, once on load, because the field and hint must agree.
- [N] (dev, iter 1) S2: are amounts in the hint plain digits with no thousands separator (1250, not 1,250)? I assume plain digits, as in the error message. -> BA decision: plain digits, because it matches the 409 message.
- [N] (dev, iter 2) S4: does the endpoint percent-decode the segment before checking it? For example, `/api/auctions/%37/minimum-bid` could be auction 7 (decoded) or 400 (raw `%`). `%207` gives 400 either way, so the ticket doesn't settle it. I would not decode, so any `%` gives 400. -> BA decision: no percent-decoding, any `%` in the segment gives 400 (`%37` included), because the page never sends encoded ids and one digits-only check on the raw segment is simplest to test.
- [N] (dev, iter 2) S4: does a method other than GET on `/api/auctions/<id>/minimum-bid` (POST, for example) get 404 `{"error": "not found"}` like other unknown routes, or 405? I would use 404. -> BA decision: 404 `{"error": "not found"}` for any method other than GET, because the baseline answers every other method and path with 404 and bidders never see it.
- [N] (dev, iter 2) S4: does "remove leading and trailing spaces" on the page mean only the space character, or all whitespace such as tabs? I would use JavaScript `trim()`. -> BA decision: all whitespace, as JavaScript `trim()` removes it, because a pasted id with a tab still means the same auction.
- [N] (dev, iter 2) S5: after a bid attempt, is the old hint cleared when the refresh request starts, or kept until the answer arrives? S2 clears the hint on every `input` event, but S5 only says what shows after the answer or a failure. I would keep the old hint until the answer, and show it empty if the lookup fails. -> BA decision: the hint is cleared when the POST finishes and stays empty until the refresh answer arrives, because the old minimum may already be stale after a bid and this matches the S2 rule.
- [N] (dev, iter 2) S5: if the page stops a bid before sending the POST (for example an empty amount), does that count as a bid attempt that triggers the refresh? The text says "once its POST has finished", so I would refresh only after a POST was actually sent. Is that right? -> BA decision: yes, only a POST that was actually sent counts; with no POST there is no refresh and the hint is left as it was, because nothing on the server changed.
