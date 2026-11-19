# Spec: Cancel a bid

Intake: [intake.md](intake.md). Baseline: [docs/baseline.md](../../docs/baseline.md).

## Summary

A bidder can **cancel** one of their own active bids, winning or outbid, from the My
bids page, within the **cancel window** of 5 minutes after placing it. The page asks
for confirmation first; there is no undo. The **cancelled bid** stays in My bids with
status `cancelled` and no standing. The auction carries on as if the bid had never
been placed: the highest bid, every standing and the minimum next bid are computed
from the remaining active bids. The bidder may bid again on the same auction.
Done means: a bidder cancels from My bids and the next request by anyone sees the
recalculated price to beat (Q13).

## Behaviour

### Who can cancel what

| Bid | Result of a cancel by user 42 |
|---|---|
| Own bid, status `active`, `now - created_at` 0 to 300000 ms (winning or outbid) | Cancelled: 200 |
| Own bid, status `active`, `now - created_at` 300001 ms or more | Refused: 409 too late, bid unchanged |
| Own bid, any status other than `active` (for example `cancelled`) | Refused: 409 not active, bid unchanged |
| Bid of another user (any status, any age) | Refused: 404 bid not found, bid unchanged |
| No bid with that id | Refused: 404 bid not found |

- The current user is the fixed web UI user `42` (baseline). The API acts as user 42.
- Checks run in this order, first failure wins: id format (400), exists and owned by
  user 42 (404), status `active` (409 not active), cancel window (409 too late).
- Cancel window: `now` is the server clock in epoch milliseconds, the same clock that
  sets `created_at`. Exactly 300000 ms after `created_at` is still allowed; 300001 ms
  is too late. A `created_at` later than `now` (clock skew) counts as inside the
  window. No time zones are involved.
- The window applies to every bid, including bids stored before this feature (Q12).
- There is no limit on how many bids a bidder may cancel (Q3), and no reason is asked (Q9).

### What a cancel changes

- The stored row gets `status = 'cancelled'`. `id`, `user_id`, `auction_id`, `amount`
  and `created_at` are unchanged. No row is deleted or added; no new column.
- The check and the update are one atomic step (one SQL `UPDATE ... WHERE id = ? AND
  user_id = ? AND status = 'active' AND created_at >= now - 300000`, or equivalent).
  Two cancels of the same bid at the same moment: exactly one gets 200, the other
  409 `bid is not active`.
- Nothing else is recomputed or stored: highest bid, standing and minimum next bid
  are already computed from active bids only (baseline), so they change by
  themselves. Examples:

| Auction before the cancel | Cancelled | Highest bid after | Minimum next bid after |
|---|---|---|---|
| 100 by user 5, 500 by user 42 | 500 | 100 by user 5 (`winning`) | 110 |
| 100 by user 42, 200 by user 5 | 100 | 200 by user 5 (unchanged) | 210 (unchanged) |
| 100 by user 42, 150 by user 42 | 150 | 100 by user 42 (`winning`) | 110 |
| 300 by user 42 only | 300 | none | 1 |
| 990 by user 5, 1000 by user 42 | 1000 | 990 by user 5 (`winning`), step back to 10 | 1000 |

- After a cancel the bidder may bid on the same auction like anyone else (Q7),
  subject to the minimum next bid; the same amount as the cancelled bid is accepted
  if it is at least the minimum next bid.
- The owner of a bid that becomes winning again gets no message (Q5).

### Core (`day-02/auction/bids.py`)

- New `cancel_bid(conn, bid_id, user_id, now_ms=None)`: `now_ms` defaults to the
  current epoch milliseconds (same source as `created_at`); tests pass it explicitly.
  Returns the bid's `auction_id` on success.
- Failures raise, with these messages (the API returns them as `error`):
  - `BidNotFoundError("bid not found")`: no such id, or the bid belongs to another user.
  - `BidNotActiveError("bid is not active")`: status is not `active`.
  - `CancelTooLateError("too late to cancel: bids can only be cancelled within 5 minutes")`.
- `list_my_bids`, `highest_bid`, `minimum_next_bid`, `place_bid` are unchanged.

### My bids list

- Unchanged from the baseline: cancelled bids stay in the list, in their place by
  (`created_at`, `id`), with `status` `"cancelled"` and `standing` `null` (Q6). The
  brief's "disappear from their list" was withdrawn by the client (intake, Contradictions).

### Page

- The table gets a sixth column, header `Cancel`. Each row whose status is `active`
  (winning or outbid, any age) has a button `Cancel bid` in it; other rows leave it empty.
- Clicking `Cancel bid` opens the browser confirm dialog (`window.confirm`) with the
  text `Cancel bid <id> on auction <auction_id> (amount <amount>)? This cannot be undone.`
  - Dialog dismissed (Cancel): no request is sent, nothing on the page changes.
  - Dialog accepted (OK): the cancel notice and the red error line are emptied, then
    `POST /api/bids/<id>/cancel` is sent. The clicked `Cancel bid` button is disabled
    until the answer arrives, so a double click sends one request; after a network
    failure it is enabled again.
- A new **cancel notice** line `id="cancel-notice"` (`aria-live="polite"`, colour
  `#666`) sits directly above the table. It is empty except after a successful cancel.
  It is emptied when a bid POST is sent or another cancel is confirmed.

| Answer to the cancel POST | Cancel notice | Red error line | Then |
|---|---|---|---|
| 200 | `Bid <id> on auction <auction_id> cancelled.` | empty | clear stored standing of that auction, reload, refresh hint |
| 404 or 409 | empty | the `error` text of the response, for example `too late to cancel: bids can only be cancelled within 5 minutes` | reload, refresh hint |
| Network failure or other status | empty | `could not cancel bid <id>` | nothing else |

- On a 404 or 409 the reload runs first and the red error line is set once the
  reload has finished, so the reload does not clear it.
- Order on 200, 404 and 409: notice and clear stored standing (200, using `auction_id`
  from the response body), reload (list fetch and render; the banner check is not
  awaited), error line (404 or 409), then refresh hint. The error line and the hint
  refresh still run if the reload fails or is superseded by a newer load.
- "Other status" includes any status other than 200, 404 or 409 and a body that is not
  JSON; like a network failure, the clicked button is enabled again.
- The Standing cell keeps its existing rendering: `-` for a cancelled bid (null standing).
- Reload means exactly what the existing Reload button does: My bids is fetched
  again from the first page with the page size field value; rows loaded with "Load
  more" are dropped. The outbid banner logic runs on that load as on any load.
- Clear stored standing: the same as after placing a new own bid on an auction (the
  entry for that auction in `localStorage` is removed), so a cancel never shows the
  outbid banner for that auction, on this reload or on a later load (Q11).
- Refresh hint: the minimum bid hint is requested again for the Auction ID field
  value at that moment, with the same rules as after a bid POST. The bid form fields
  keep their values.

## API and page

Changes to the baseline web app (`day-11/webapp`):

| Method and path | Result |
|---|---|
| `POST /api/bids/<bid_id>/cancel` (new) | 200 `{"id": 31, "auction_id": 7, "status": "cancelled"}`; 400 `{"error": "invalid bid_id"}`; 404 `{"error": "bid not found"}`; 409 `{"error": "bid is not active"}`; 409 `{"error": "too late to cancel: bids can only be cancelled within 5 minutes"}` |
| `GET /api/bids` | Unchanged (cancelled bids listed with `status` `"cancelled"`, `standing` null) |
| `GET /api/auctions/<auction_id>/minimum-bid` | Unchanged; reflects cancels on the next request |

- `<bid_id>` follows the same rules as `<auction_id>` on the minimum-bid route: one
  path segment of digits 0-9 only, leading zeros allowed (`031` -> 31), value 1 to
  2^63-1, not percent-decoded; anything else (`abc`, `0`, `-1`, `1.5`, empty,
  9223372036854775808) is 400 `{"error": "invalid bid_id"}`.
- The request body is ignored (none needed). The query string is ignored.
- A trailing slash, an extra segment or `;params` on this path, and any method other
  than POST on it, answer 404 `{"error": "not found"}`. `POST /api/bids` is unchanged.
- Page: new `Cancel` column with `Cancel bid` buttons, confirm dialog, cancel notice
  line (see Behaviour). Form, hint, page size, Load more and outbid banner otherwise
  unchanged.

## Out of scope

- Hiding cancelled bids from My bids, or a separate "show cancelled" view (Q6).
- Undo of a cancel, or cancelling without confirmation (Q4).
- Cancelling another user's bid, or support/admin cancelling on a bidder's behalf.
- Editing the amount or auction of a bid; the bidder cancels and bids again (Q10).
- A reason for cancelling (Q9).
- A limit on the number of cancels per bidder, day or auction (Q3).
- A message or banner for a bidder who becomes winning again after a cancel (Q5).
- The outbid banner as a result of a cancel (Q11).
- A count or report of cancelled bids, or a `cancelled_at` time (Q13 answer (a)).
- Live push or polling: other bidders see the new price on their next request or load.
- Login, several users in the UI, auction end, notifications.

## Tickets

- [T-01 Cancel a recent bid from My bids](tickets/T-01-cancel-recent-bid.md): cancel endpoint, confirm dialog, button disabled in flight, row shows `cancelled`, notice, not found, not active (API and page), invalid id.
- [T-02 Limit cancels to five minutes](tickets/T-02-five-minute-window.md): window boundary, too-late message on API and page, old bids, double cancel, no count limit.
- [T-03 Recalculate the auction after a cancel](tickets/T-03-recalculate-after-cancel.md): highest bid, standings, minimum next bid, bidding again, all bids cancelled.
- [T-04 Keep the page in step after a cancel](tickets/T-04-page-after-cancel.md): list reload, hint refresh, no outbid banner, network failure.
