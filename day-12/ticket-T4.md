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
