# T-02 Limit cancels to five minutes

Status: ready
Issue: #25
Dev rounds: 1
Spec: [Cancel a bid](../spec.md#who-can-cancel-what)

## Story

As a bidder
I want to be told clearly when a bid is too old to cancel
So that cancelling stays a way to fix mistakes and cannot be used to play with the price later

## Scenarios

### S1 Cancel at exactly five minutes is accepted

Given bid 41 of 200 by user 42 on auction 8 is active with `created_at` 1793613600000 (2026-11-02 10:00:00.000 UTC)
When `cancel_bid(conn, 41, 42, now_ms=1793613900000)` is called (10:05:00.000 UTC, 300000 ms later)
Then it returns auction id 8 and the stored row of bid 41 has status `cancelled`

### S2 Cancel one millisecond later is refused

Given bid 41 of 200 by user 42 on auction 8 is active with `created_at` 1793613600000
When `cancel_bid(conn, 41, 42, now_ms=1793613900001)` is called
Then it raises `CancelTooLateError` with message `too late to cancel: bids can only be cancelled within 5 minutes`
And the stored row of bid 41 still has status `active`
And when `now_ms` is omitted, `cancel_bid` uses `int(time.time() * 1000)`, the same expression `place_bid` uses for `created_at`

### S3 Too late on the API and the page

Given bid 42 of 300 by user 42 on auction 9 is active with `created_at` equal to the server clock minus 360000 ms (6 minutes ago), inserted straight into the store the server uses
When user 42 clicks `Cancel bid` on bid 42 in My bids and accepts the dialog
Then `POST /api/bids/42/cancel` returns 409 `{"error": "too late to cancel: bids can only be cancelled within 5 minutes"}`
And the red error line shows `too late to cancel: bids can only be cancelled within 5 minutes`, the cancel notice is empty
And after the reload the row of bid 42 still shows Status `active` and its `Cancel bid` button
And the server calls `cancel_bid` without `now_ms` (real clock); no clock setting is added to the server or the API

### S4 Bids stored before the feature follow the same window

Given bid 43 of 150 by user 42 on auction 10 is an active row inserted straight into the store with `created_at` equal to the server clock minus 120000 ms (2 minutes ago), and bid 44 of 160 by user 42 on auction 10 is an active row inserted the same way with `created_at` minus 3600000 ms (1 hour ago)
When the client sends `POST /api/bids/43/cancel`, then `POST /api/bids/44/cancel`
Then bid 43 answers 200 `{"id": 43, "auction_id": 10, "status": "cancelled"}` and is stored as `cancelled`
And bid 44 answers 409 `{"error": "too late to cancel: bids can only be cancelled within 5 minutes"}` and stays `active`

### S5 Two cancels of the same bid at the same moment

Given bid 45 of 120 by user 42 on auction 11 is active and was placed 60000 ms before the cancels
When two cancels of bid 45 run at the same moment (two threads calling `cancel_bid` on the core is enough; the server lock already serialises HTTP requests)
Then exactly one succeeds (200 on the API, returns 11 on the core) and the other fails with `bid is not active` (409 on the API, `BidNotActiveError` on the core)
And bid 45 is stored once, with status `cancelled`
And when the atomic `UPDATE` changes no row, the row is read again and the error follows the spec check order: missing or other user -> `bid not found`, status not `active` -> `bid is not active`, otherwise -> `too late to cancel: bids can only be cancelled within 5 minutes`

### S6 No limit on the number of cancels

Given user 42 has three active bids 46, 47 and 48 on auctions 12, 13 and 14, each placed 60000 ms before the cancels
When the client sends `POST /api/bids/46/cancel`, `/47/cancel` and `/48/cancel` one after another
Then all three answer 200 with `auction_id` 12, 13 and 14 respectively, and all three bids are stored as `cancelled`

## Out of scope

- A per-day, per-auction or total limit on cancels.
- Hiding the `Cancel bid` button on rows older than 5 minutes: the button shows on every active row and the server answers.
- A countdown or a display of the time left to cancel.
- Time zones: the window is measured in epoch milliseconds on the server clock.
- A clock hook or `now_ms` parameter on the server or the API; only the core `cancel_bid` takes `now_ms`.
- Checking other auctions in S6: their effect on the highest bid is covered in T-03.

## Questions

- [N] (dev, iter 1) S3 and S4 need bids placed 6 minutes, 2 minutes or 1 hour ago, but the server calls `cancel_bid` without `now_ms`. Is it fine for the API tests to insert rows with an old `created_at` straight into the shared connection (or patch the clock helper), instead of adding a clock hook to the server? -> answered in ticket body (iter 1)
- [N] (dev, iter 1) S5 sends two cancels at once. The server lock already serialises requests, so should the test just use two threads against the core function or the server? Does the atomic `UPDATE` then reread the row to choose between `bid is not active` and `too late`, in the spec's check order? -> answered in ticket body (iter 1)
- [N] (dev, iter 1) S6 asks for all three cancels to answer 200. Should the test also check that the three auctions (12, 13, 14) are unaffected by each other, or is the stored status of the three bids enough? -> BA decision: the three 200 answers with their `auction_id` and the stored status of the three bids are enough, because the effect of a cancel on an auction is T-03's subject and S6 is only about the absence of a count limit.
- [N] (dev, iter 1) S2 and S3 expect the window to be measured with an integer `now_ms`. For the default clock, should `now_ms` be `int(time.time() * 1000)`, the exact expression `place_bid` uses for `created_at`? I will reuse that expression. -> answered in ticket body (iter 1)
