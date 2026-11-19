# Evidence: Playwright MCP, end to end

Run on 2026-11-03 by Claude with the Playwright MCP tools (`@playwright/mcp@0.0.84`, set up in
`.mcp.json`) against the demo app `python .claude/skills/evidence/seed_server.py 8010`. Claude
did every step; nothing was done by hand. The server was stopped and the browser closed afterwards.

## Steps, in order

1. `browser_navigate` to http://127.0.0.1:8010/. The page lists the user's bids (bid 6 cancelled,
   bid 5 active and Winning). The only console error is the missing `favicon.ico` (404).
2. `browser_fill_form`: Auction ID `7`, Amount `120`. `browser_click` on `Place bid`.
   Auction 7 has a highest bid of 150, so the minimum is 160. The page shows the alert
   `bid must be at least 160` and the hint `Minimum next bid: 160`. The POST answered 409.
   Screenshot: `01-bid-below-minimum-error.png`.
3. `browser_fill_form`: Amount `160`. `browser_click` on `Place bid`. The POST answered 201.
4. `browser_click` on `Reload` to read the list back. `browser_snapshot` and
   `browser_take_screenshot` saved `02-after-valid-bid-snapshot.md` and
   `02-after-valid-bid-read-back.png`: bid 8 on auction 7, amount 160, active, Winning; the hint
   moved to `Minimum next bid: 170`.
5. `browser_network_requests` (filter `/api/`) saved `network.txt`: GET list, GET minimum, POST 409,
   GET minimum, POST 201, GET minimum, GET list.
6. `browser_close`.

## Files

| File | Shows |
|---|---|
| `01-bid-below-minimum-error.png` | The failing case: error line for a bid below the minimum |
| `02-after-valid-bid-read-back.png` | The list read back after the valid bid |
| `02-after-valid-bid-snapshot.md` | The same page as an accessibility snapshot (text) |
| `network.txt` | The API calls in order, with the 409 and the 201 |

## Limits

- The demo data is seeded by the script, so bid 6 and bid 5 are from the seed, not from this run.
- Only the bid form and the list were driven. Cancel was not part of this run; its evidence is in
  `../T-01` to `../T-04`, captured with Claude in Chrome.
