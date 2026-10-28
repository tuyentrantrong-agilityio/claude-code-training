# T4 (optional): Outbid hint since last view

**Depends on:** T1, T2

## Story

As a bidder, I want a hint when I was beaten since I last looked, so that I can react.

## Acceptance criteria

- Given a bid was `winning` at the last page load and is `outbid` now, then the
  page shows a banner "You were outbid on auction N".
- Given nothing changed, then no banner is shown.

## Open questions

- Client said in-page only, no email. Where is "last view" kept (browser or
  server), and must it survive a reload? Open.

## Dev questions (write here)

(none yet)

## Decisions taken while implementing

- Last known standing per auction is kept in the browser (localStorage), so it
  survives reloads. The banner shows after a load when a stored "winning"
  became "outbid".
- Placing your own new bid on an auction clears its stored standing, so
  self-outbid does not raise the banner.
- The web UI has a single fixed user, so the banner cannot be triggered from
  the UI by another bidder; only the logic is in place. Manual check: in the
  browser console set localStorage standing to {"7":"winning"} for a bid that
  is outbid, then Reload.

## Browser check (Day 13)

- Found: the banner showed on the very first load with no history, because rows
  of one auction were compared with each other (a winning bid, then an older
  outbid bid on the same auction).
- Fix: the check uses its own request (limit 100), an auction counts as winning
  if any bid on it is winning, and it is compared with the stored standing
  from the previous load.
- Re-checked in the browser: no banner on first or second load, banner shown when
  the API answer is mocked as outbid, no banner after placing an own higher bid.
  Limit: only the first 100 bids are checked.
