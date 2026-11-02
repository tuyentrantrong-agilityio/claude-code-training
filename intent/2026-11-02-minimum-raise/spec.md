# Spec: Minimum raise on bids

Intake: [intake.md](intake.md). Baseline: [docs/baseline.md](../../docs/baseline.md).

## Summary

A new bid must beat the highest bid of its auction by a **minimum step**: 10 while
the highest amount is under 1000, 50 when it is 1000 or more. A too-low bid is
refused with a message naming the **minimum next bid**. The first bid on an auction
stays free. The bid form shows the minimum next bid for the auction the bidder typed
(the **minimum bid hint**). Bids placed before the change are left alone.

## Behaviour

### Minimum step and minimum next bid

| Highest active amount H on the auction | Minimum step | Minimum next bid |
|---|---|---|
| No active bid (never bid, or all bids cancelled) | none | 1 |
| 1 to 999 | 10 | H + 10 |
| 1000 or more | 50 | H + 50 |

- H is the amount of the highest bid as defined in the baseline (active bids only;
  cancelled and other non-active bids are ignored, whatever their amount).
- The tier is chosen by H, not by the offered amount: H 999 -> minimum 1009;
  H 990 -> minimum 1000; H 1000 -> minimum 1050.
- A bid is accepted when `amount >= minimum next bid`. Exactly the minimum is accepted.
- The rule applies to every bidder, including the bidder who already holds the
  highest bid (raising your own bid also needs the step).
- Amounts stay whole numbers (euros), 1 to 2^63-1, validated as in the baseline
  (400 for missing, non-integer, below 1 or too large). The 400 checks run before
  the minimum check.
- If H + step is above 2^63-1, no allowed amount can be accepted: every new bid on
  that auction gets 409 naming H + step (for example H 9223372036854775800 ->
  "bid must be at least 9223372036854775850").

### Rejection

- A bid below the minimum next bid is not stored and is answered with 409
  `{"error": "bid must be at least <minimum next bid>"}`, for example
  `bid must be at least 110`. This replaces `bid must be higher than <highest>`.
- In `day-02/auction/bids.py` the exception stays `BidTooLowError`; its message
  becomes `bid must be at least <minimum next bid>`.
- On the page the message appears in the existing red error line, and the Amount and
  Auction ID fields keep what the bidder typed.

### Concurrency

- The check and the insert stay one atomic step (as in the baseline). Bids sent at
  the same moment are checked one after the other: the first stored becomes the
  highest bid and the next is checked against it. Highest 100, two bids of 110 at
  once: exactly one is stored (201), the other gets 409 `bid must be at least 120`.

### Existing data

- Bids already stored are never changed, removed or re-checked. Their status and
  standing stay as computed by the baseline rules. Only bids placed after the change
  must respect the step. Example: auction 7 holds 100 (user 5) then 101 (user 42),
  both from before; 101 is still `winning` and the next bid must be at least 111.
- Existing tests that assert the old `bid must be higher than` message or an accepted
  raise of 1 describe the old rule and are updated to the new rule.

### Minimum bid hint

| Auction ID field | Hint line text |
|---|---|
| Empty, not a whole number, or below 1 | (empty, no request sent) |
| Auction with no active bid | `No bids yet: any amount from 1` |
| Auction with highest bid H | `Minimum next bid: <H + step>` |
| Lookup request fails (non-200) | (empty) |

- The hint is a line under the Amount field of the bid form (`id="min-bid-hint"`,
  `aria-live="polite"`, colour `#666`, normal size). Amounts are plain digits.
- A valid Auction ID value: leading and trailing whitespace removed (JavaScript `trim()`), then only digits 0-9,
  value 1 to 2^63-1; it is sent with leading zeros removed (" 007 " -> auction 7).
- It is requested on every `input` event of the Auction ID field, once on page load
  if the field has a value, and after every bid attempt once its POST has finished
  (any result, network failure included), using the field value at that moment.
  A bid attempt is a `POST /api/bids` actually sent; no POST, no refresh.
  On each change, and when a bid POST finishes, the hint is cleared at once. If several lookups are in flight, only
  the answer for the value currently in the field is shown. There is no timed polling.
- The hint text comes only from the lookup response. After a bid attempt the Auction
  ID and Amount fields keep their values (201 and 409 alike).
- The hint is help only: the server check on `POST /api/bids` decides.

## API and page

Changes to the baseline web app (`day-11/webapp`):

| Method and path | Result |
|---|---|
| `POST /api/bids` `{"auction_id", "amount"}` | Unchanged except the too-low case: 409 `{"error": "bid must be at least <minimum next bid>"}` |
| `GET /api/auctions/<auction_id>/minimum-bid` (new) | 200 `{"auction_id": 7, "highest": 100, "step": 10, "minimum_bid": 110}`; for an auction with no active bid 200 `{"auction_id": 7, "highest": null, "step": null, "minimum_bid": 1}`; 400 `{"error": "invalid auction_id"}` when `<auction_id>` is not a whole number from 1 to 2^63-1 |

- The `<auction_id>` segment is one path segment (empty included): only digits 0-9,
  leading zeros allowed (007 -> 7), value 1 to 2^63-1, else 400. A trailing slash or
  extra segment is 404 `{"error": "not found"}`. The query string is ignored. The
  segment is not percent-decoded (any `%` gives 400). Any method other than GET on
  this path is 404 `{"error": "not found"}`.
  `minimum_bid` is the exact integer H + step, even above 2^63-1 (status 200).
- An auction id that has never had a bid is not a 404: it answers like an auction with
  no active bid (`minimum_bid` 1), since auctions exist only through bids.
- Page: bid form gains the minimum bid hint line (see Behaviour). Table, Load more,
  page size and outbid banner are unchanged.

## Out of scope

- Reporting or proof that final prices went up (Q11).
- Changing the step, from the page or per auction (Q9).
- Amounts with cents (Q8).
- Showing the minimum next bid in the My bids table (Q6 option b not chosen).
- Filling the Amount field with the minimum automatically (Q10: the typed amount stays).
- Re-checking, cancelling or flagging bids placed before the change (Q5).
- Auction end, winner, end time, notifications.
- Exact display of amounts above 2^53 in the browser.

## Tickets

- [T-01 Reject bids below the minimum](tickets/T-01-reject-below-minimum.md): step tiers, exact-minimum acceptance, 409 message on API and page, free first bid.
- [T-02 Apply the minimum to every bid](tickets/T-02-minimum-for-every-bid.md): own raises, cancelled bids, old bids, simultaneous bids, overflow.
- [T-03 Show the minimum next bid](tickets/T-03-show-minimum-next-bid.md): new lookup endpoint and the minimum bid hint in the bid form.
