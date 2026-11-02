# Evidence for the bid standing web app (2026-11-02)

All files here were produced by Claude, not by hand.

## Browser run (Claude in Chrome MCP tools)

Claude started day-11 webapp on port 8010 with demo data and drove it in a
new Chrome tab (navigate, find, computer click/type/screenshot, javascript_tool).

| File | What it shows |
|---|---|
| 01-first-load-no-banner.jpg | First visit with empty localStorage: no outbid banner |
| 02-standing-column.jpg | Page size 10: Winning (green), Outbid (red), "-" for a cancelled bid |
| 03-low-bid-rejected-409.jpg | Bid 100 on auction 8 (highest 300): "bid must be higher than 300" |
| 04-higher-bid-accepted.jpg | Bid 400 on auction 8: new bid Winning, old own bid Outbid |
| 05-outbid-banner.jpg | localStorage set to winning for auction 7, reload: outbid banner |

Limits: the web app has one fixed user, so the competing bid from user 5 was
inserted into the database by a launcher script, and the banner was triggered
by writing localStorage through the javascript tool.

## Test output

- test-day-02.txt: day-02 unit tests (20 tests, OK)
- test-day-11.txt: day-11 web tests (14 tests, OK)
- test-hook.txt: hook tests (11 tests, OK)

## Shared page

The same run is published as a Claude artifact: https://claude.ai/artifact/AuymGPyna4oTLg8cULs2V5
