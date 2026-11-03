# Baseline: the auction app as it exists

The product behind this repo is a small auction platform. New features are
briefed and specified on top of this page. If the code and this page disagree,
the code wins and this page is fixed in the same merge request.

## Users

One kind of user, a **bidder**. There is no login: the web UI acts as one fixed
user, id `42` (`USER` in `day-11/webapp/server.py`). Other bidders exist only in
the data (for example user `5` in tests and demo data).

## Data

SQLite, one table, created by `SCHEMA` in `day-02/auction/bids.py`.

| Field | Type | Rules |
|---|---|---|
| `id` | integer | Assigned by SQLite, increasing |
| `user_id` | integer | Required |
| `auction_id` | integer | Required, 1 or more (checked by the web API) |
| `amount` | integer | Required, 1 or more (checked by the web API), at most 2^63-1 |
| `status` | text | `active` by default; any other value (for example `cancelled`) means the bid no longer counts |
| `created_at` | integer | Epoch milliseconds |

There is no auction table: an auction exists as soon as it has a bid.

## Rules

- **Highest bid** of an auction: the `active` bid with the largest amount; on equal
  amounts the earliest `created_at`, then the lowest `id` (`highest_bid`).
- **Placing a bid** (`place_bid`): accepted only if the amount is at least the
  **minimum next bid** of that auction: highest active amount H plus the **minimum step**
  (10 while H is under 1000, 50 from 1000), from any user, including the bidder's own.
  The first bid on an auction may be any amount (`minimum_next_bid` is 1). The check
  and the insert are one SQL statement, so of several equal bids sent at once exactly
  one is stored. A rejected bid raises `BidTooLowError` with the message
  `bid must be at least <minimum next bid>`. (Since T-01, intent/2026-11-02-minimum-raise.)
- **Standing** of a bid in a listing: `winning` if it is the highest bid of its
  auction, `outbid` if it is active but not the highest, `null` if it is not active.
- **My bids** (`list_my_bids`): the user's bids, newest first by (`created_at`, `id`).
  `limit` must be 1 to 100. `next_cursor` is set when a full page was returned and
  is an opaque base64 string; a malformed cursor raises `ValueError("invalid cursor")`.

## Web app (`day-11/webapp`)

`python -m webapp.server` from `day-11` serves http://127.0.0.1:8000. Data is in
memory and resets on restart. One shared connection is guarded by a lock.

| Method and path | Result |
|---|---|
| `GET /` | The "My bids" page (`index.html`) |
| `GET /api/bids?limit=&cursor=` | 200 `{"items": [...], "next_cursor": ...}`; 400 `{"error": ...}` for a bad limit or cursor |
| `POST /api/bids` `{"auction_id", "amount"}` | 201 `{"id": n}`; 400 if a value is missing, not an integer (floats and booleans too), below 1 or too large; 409 `bid must be at least <minimum next bid>` |
| `GET /api/auctions/<auction_id>/minimum-bid` | 200 `{"auction_id", "highest", "step", "minimum_bid"}` (`highest` and `step` null and `minimum_bid` 1 with no active bid); 400 `{"error": "invalid auction_id"}` unless the raw segment is digits with value 1 to 2^63-1 |
| `POST /api/bids/<bid_id>/cancel` | 200 `{"id", "auction_id", "status": "cancelled"}` for the user's own active bid; 400 `{"error": "invalid bid_id"}` unless the raw segment is digits with value 1 to 2^63-1 (leading zeros allowed); 404 `{"error": "bid not found"}` for an unknown bid or another user's bid; 409 `{"error": "bid is not active"}`; 409 `{"error": "too late to cancel: bids can only be cancelled within 5 minutes"}` when more than 300000 ms (server clock, epoch milliseconds) passed since the bid was placed; exactly 300000 ms is still in time. Checks run in the order not found, not active, too late. Body and query string are ignored. (Since T-01 and T-02, intent/2026-11-02-cancel-bid.) |
| anything else (other paths, `minimum-bid;params`, a cancel path with a trailing slash, `;params` or an extra segment, any other method; HEAD gets the 404 headers only) | 404 `{"error": "not found"}` |

`GET /` and `GET /api/bids` ignore `;params` in the path (they read it through `urlparse`);
only the minimum-bid route treats them as an unknown path.

The page has a form (Auction ID, Amount, minimum bid hint, Place bid), a page size field with
Reload, a cancel notice line (`id="cancel-notice"`, above the table), a table (ID, Auction,
Amount, Status, Standing, Cancel) with "Load more", a red error line, and an outbid
banner "You were outbid on auction N". Each active row has a `Cancel bid` button: after
the browser confirm dialog it sends the cancel, the button stays disabled until the answer
arrives, a 200 sets the notice "Bid N on auction M cancelled." and reloads My bids, and a
404 or 409 reloads first and then shows the error text in the red line (T-01); the button shows on every active row whatever its age, and the server decides (T-02). The banner
compares the standing per auction with the one kept in `localStorage` from the
previous load, using its own request for the first 100 bids. Placing a new own
bid on an auction clears its stored standing. The minimum bid hint
(`id="min-bid-hint"`) reads "Minimum next bid: N" or "No bids yet: any amount from 1",
from the lookup sent on each Auction ID input, on load and after each bid POST; it is
empty for an invalid id or a failed lookup. Both form fields keep their values after a bid.
(Since T-03, intent/2026-11-02-minimum-raise.)

## Other code

`day-04/shop` (cart and pricing) is a separate exercise and is not part of the product.

## Not in the baseline

Login and several users in the UI, an auction table (title, end time), a step set
per auction, auction end and winner, notifications by email or push, payments.
