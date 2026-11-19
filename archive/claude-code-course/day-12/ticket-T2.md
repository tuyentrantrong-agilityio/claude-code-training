# T2: Show standing column in the web table

**Component:** `day-11/webapp/index.html`
**Depends on:** T1

## Story

As a bidder, I want to see "Winning" or "Outbid" on each row of My Bids.

## Acceptance criteria

- Given the list API returns `standing`, when the table renders, then each row
  shows "Winning" or "Outbid" in a new column.
- Given a row is `outbid`, then it looks different from `winning`, and colour
  is not the only cue (the word is shown).
- Given "Load more" appends rows, then the new rows show standing too.
- Given an API error, then the existing red error message and hidden
  "Load more" behaviour are unchanged.

## Open questions

- Q8 (BA): exact labels and colours? Proposed: "Winning" green, "Outbid" red.

## Dev questions (write here)

(none yet)

## Decisions taken while implementing

- Q8: labels "Winning" (green) and "Outbid" (red), text always shown.
- Not covered by automated tests (HTML); needs a manual browser check.

## BA reply (Day 13)

- Q8 confirmed: "Winning" green and "Outbid" red, word always shown.
