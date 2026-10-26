# Day 11 - Developer role day (web)

Small web UI over `day-02/auction` so the running product can be driven from a
browser session instead of only reading code.

## Run

    cd day-11
    python -m webapp.server        # http://127.0.0.1:8000
    python -m unittest discover -s tests -t . -v

Endpoints: `GET /`, `GET /api/bids?limit=&cursor=`, `POST /api/bids`.
Data is in memory and resets on restart. If the page shows old bids, a previous
server is still holding port 8000; stop it before starting a new one.

## Browser check with Claude in Chrome

Run against the live server in a new Chrome tab.

| Step | Result |
|---|---|
| Open the page | Table shows the latest bids, page size 2, "Load more" visible |
| Fill auction 9, amount 250, submit | Bid 4 appears at the top; console: `placed bid 4` |
| Amount -5, submit | Red message "auction_id and amount must be positive"; console error logged |
| Page size 0, Reload | Red message "limit must be between 1 and 100" (the Day 10 limit rule) |

## Bug found in the browser

After Reload with an invalid page size the table was cleared but the
"Load more" button stayed visible. Cause: `load(true)` reset the rows but not
the button, and the early return on error skipped the update. Fix: hide the
button in the reset step. Re-checked in the browser: the button stays hidden.

## Notes

- Tests do not cover the HTML; the bug above was only visible in the browser.
- The GIF recording was captured (6 frames) but not exported.
