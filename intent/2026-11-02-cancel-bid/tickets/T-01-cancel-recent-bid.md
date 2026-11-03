# T-01 Cancel a recent bid from My bids

Status: ready
Issue: #24
Dev rounds: 1
Spec: [Cancel a bid](../spec.md#behaviour)

## Story

As a bidder
I want to cancel one of my own bids from the My bids page, after confirming
So that I can fix a wrong amount or a wrong auction without writing to support

## Scenarios

All bids below were placed 1 minute before the cancel; the age is only a fixture; T-01 does not check it (the window is T-02).

### S1 Cancel an own active bid through the API

Given auction 7 has bid 30 of 100 by user 5 and bid 31 of 500 by user 42, placed 1 minute ago, both active
When the client sends `POST /api/bids/31/cancel`
Then the API returns 200 `{"id": 31, "auction_id": 7, "status": "cancelled"}`
And the stored row of bid 31 has status `cancelled` with `user_id` 42, `auction_id` 7, amount 500 and `created_at` unchanged
And `GET /api/bids` still lists bid 31 with `"status": "cancelled"` and `"standing": null`

### S2 Cancel from the page after confirming

Given My bids shows bid 31 (auction 7, amount 500, Status `active`, Standing `winning`) with a `Cancel bid` button in the `Cancel` column
When user 42 clicks `Cancel bid` on bid 31 and accepts the dialog `Cancel bid 31 on auction 7 (amount 500)? This cannot be undone.`
Then the `Cancel bid` button of bid 31 is disabled from the moment the dialog is accepted until the answer arrives, so a second click sends no second POST
And the cancel notice reads `Bid 31 on auction 7 cancelled.` and the red error line is empty
And My bids is reloaded exactly as the Reload button does, and the row of bid 31 shows Status `cancelled`, Standing `-` and no `Cancel bid` button

### S3 Dismissing the dialog changes nothing

Given My bids shows bid 31 on auction 7 as active and winning
When user 42 clicks `Cancel bid` on bid 31 and dismisses the dialog
Then no `POST /api/bids/31/cancel` request is sent
And the row of bid 31 still shows Status `active`, Standing `winning` and its enabled `Cancel bid` button, and the cancel notice is empty

### S4 Bid of another user or unknown bid

Given bid 30 of 100 on auction 7 belongs to user 5 and is active, and no bid has id 999 or 9223372036854775807
When the client sends `POST /api/bids/30/cancel`, `POST /api/bids/999/cancel` and `POST /api/bids/9223372036854775807/cancel`
Then each answers 404 `{"error": "bid not found"}`
And bid 30 is still stored with status `active`

### S5 Bid that is already cancelled, on the API and the page

Given My bids shows bid 31 of user 42 on auction 7 as active with its `Cancel bid` button, but bid 31 has since been cancelled in another tab (stored status `cancelled`)
When user 42 clicks `Cancel bid` on bid 31 and accepts the dialog
Then `POST /api/bids/31/cancel` returns 409 `{"error": "bid is not active"}` and the stored row is unchanged
And My bids is reloaded first, and once that reload has finished the red error line is set to `bid is not active` (so the reload does not clear it); the cancel notice is empty
And after the reload the row of bid 31 shows Status `cancelled` with no `Cancel bid` button
And a 404 answer is handled the same way, with the red error line showing `bid not found`

### S6 Invalid bid id

Given bid 31 of 500 by user 42 on auction 7 is active
When the client sends `POST` to `/api/bids/abc/cancel`, `/api/bids/0/cancel`, `/api/bids/-1/cancel`, `/api/bids/1.5/cancel`, `/api/bids//cancel` (empty segment) and `/api/bids/9223372036854775808/cancel`
Then each answers 400 `{"error": "invalid bid_id"}` and bid 31 is still `active`
And `GET /api/bids/31/cancel` and `POST /api/bids/31/cancel/` answer 404 `{"error": "not found"}`
And then `POST /api/bids/031/cancel` answers 200 `{"id": 31, "auction_id": 7, "status": "cancelled"}` (leading zeros allowed)

## Out of scope

- The 5 minute cancel window, its check in `cancel_bid` and `CancelTooLateError` (T-02). T-01 builds `cancel_bid(conn, bid_id, user_id, now_ms=None)` with that final signature and the checks id, owner, status; `now_ms` is accepted but not used until T-02.
- Clearing the stored standing of the auction and refreshing the minimum bid hint after a cancel (T-04). T-01 only reloads My bids.
- Effects on the highest bid, standings and minimum next bid of the auction (T-03).
- Outbid banner handling, network failures and re-enabling the button after a network failure (T-04).
- Undo, a reason for cancelling, editing a bid, cancelling another user's bid.

## Questions

- [N] (dev, iter 1) T-01 puts the 5-minute window out of scope (T-02), but `cancel_bid` has one signature and a fixed check order. Should I build T-01 without the window check and without `CancelTooLateError`, leaving them to T-02? Or should I build the whole function now, so that S1's "placed 1 minute ago" is only a fixture? -> BA decision: build `cancel_bid` with its final signature now, without the window check and `CancelTooLateError` (both T-02); the 1 minute age is only a fixture, because each ticket stays a thin slice and T-02 adds the last check in the spec's order.
- [N] (dev, iter 1) S2 only covers the 200 flow on the page. The spec's 200 row also says "clear stored standing, refresh hint", which T-04 covers. Should T-01 implement the reload only, and leave clearing the stored standing and the hint refresh to T-04? -> BA decision: T-01 implements the reload only; clearing the stored standing and the hint refresh are T-04, because T-04 owns all page side effects of a cancel and its scenarios test them.
- [N] (dev, iter 1) The page's handling of 404 and 409 (the `error` text shown in the red line, then a reload) is not in any T-01 scenario. Is it in T-01 or T-04? The ticket only excludes network failures. -> BA decision: in T-01 (S5), with the error text set after the reload finishes, because T-02 (built next) shows its too-late message on the page through the same path.
- [N] (dev, iter 1) Should the `Cancel bid` button be disabled while its POST is in flight, to stop a double click sending two requests? The spec doesn't say. -> BA decision: yes, the clicked button is disabled from accepting the dialog until the answer arrives (S2), because a second POST would only produce a confusing `bid is not active` error.
- [N] (dev, iter 1) S6 lists `abc`, `0` and `9223372036854775808` for the 400. Should the tests also cover `031` (accepted as 31), `-1`, `1.5` and an empty segment, as the spec says? Also, for `/api/bids//cancel`, is an empty segment a 400 or a 404? -> answered in ticket body (iter 1)
