# T-04 Keep the page in step after a cancel

Status: ready
Issue: #27
Dev rounds: 3
Spec: [Cancel a bid](../spec.md#page)

## Story

As a bidder
I want My bids, the minimum bid hint and the outbid banner to reflect my cancel at once
So that I can bid again on the right amount without being misled

## Scenarios

All bids below were placed less than 5 minutes before the cancel, unless stated.

Rules that apply to every scenario (spec, Page):

- The order after any 200, 404 or 409 answer is, one step after the other:
  1. 200 only: set the cancel notice and clear the stored standing of the auction
     named by `auction_id` in the 200 response body (not the row's value).
  2. Run the same reload as the Reload button and wait for it to finish. "Finished"
     means the list fetch and the table render only; the outbid banner check that the
     reload starts is not awaited and runs on its own, as on any load today.
  3. 404 or 409 only: set the red error line to the `error` text of the cancel
     response. The reload's own `showError("")` therefore runs before this step and
     never wipes the cancel error.
  4. Refresh the minimum bid hint (on 200, 404 and 409).
- If the reload in step 2 fails (for example its fetch rejects), the cancel flow catches
  that failure, shows nothing extra for it, and still runs steps 3 and 4.
- If the reload in step 2 is superseded by a newer load (Reload, Place bid or another
  cancel, through `loadSeq`) and returns early, steps 3 and 4 still run once it has
  returned. A newer load that finishes later may clear the red error line, as any load
  does today.
- The hint refresh in step 4 reads the Auction ID field when step 4 runs, not when the
  button was clicked. It uses the same rules as after a bid POST (empty hint for an
  invalid id or a failed lookup).
- Any other answer (network failure, a status other than 200, 404 or 409 such as 400
  or 500, or a body that is not JSON): the red error line shows
  `could not cancel bid <id>`, the cancel notice is empty, the clicked `Cancel bid`
  button is enabled again, and there is no reload, no hint refresh and no change to
  the stored standing.
- The Standing cell keeps the page's existing rendering: a null standing (every
  cancelled bid) shows `-`, and a `winning` or `outbid` standing shows the same label
  the page shows today (for example `Winning`). The Status cell shows the `status`
  value (`active`, `cancelled`). In the scenarios below, "Standing `winning`" means the
  cell shows the existing label for `winning`.
- The clicked `Cancel bid` button is disabled from the POST until the answer arrives
  (built in T-01); this ticket only relies on it.

### S1 Other rows of the auction update after a cancel

Given My bids (page size 2, after one "Load more") shows bid 61 of 150 (`winning`) and bid 60 of 100 (`outbid`) on auction 9, both by user 42, plus older rows
When user 42 cancels bid 61 from the page and confirms
Then My bids is reloaded from the first page with page size 2, so only the first 2 rows are shown
And bid 61 shows Status `cancelled` with Standing `-`, and bid 60 shows Status `active` with Standing `Winning`
And the 2 rows shown are whatever the first page of `GET /api/bids?limit=2` returns after the cancel, even if they differ from the first 2 rows shown before

### S2 The minimum bid hint refreshes after a cancel

Given the Auction ID field holds 7 and the Amount field holds 120, auction 7 has bid 30 of 100 by user 5 and bid 31 of 500 by user 42, and the hint reads `Minimum next bid: 510`
When user 42 cancels bid 31 from the page and confirms
Then after My bids has been reloaded, the hint reads `Minimum next bid: 110`
And the Auction ID field still holds 7 and the Amount field still holds 120

### S3 A cancel never shows the outbid banner

Given auction 20 has bid 80 of 100 by user 42, bid 81 of 110 by user 5 and bid 82 of 120 by user 42, and the last page load stored auction 20 as `winning`
When user 42 cancels bid 82 from the page, and then reloads the browser page
Then the banner `You were outbid on auction 20` is not shown after the cancel nor after the browser reload
And My bids lists bid 80 with Status `active` and the existing label for `outbid` in Standing, and bid 82 with Status `cancelled` and Standing `-`

### S4 The banner still shows for a real outbid after a cancel

Given user 42 has cancelled a bid on auction 20 as in S3, and holds bid 83 of 130 on auction 21 that was `winning` at the last page load
When user 5 bids 140 on auction 21 and user 42 reloads the browser page
Then the banner `You were outbid on auction 21` is shown, and no banner for auction 20

### S5 Cancel failed on the server

Given bid 31 of 500 on auction 7 is shown as active in this tab but was cancelled in another tab, which cleared the stored standing of auction 7 and reloaded (auction 7 now has bid 30 of 100 by user 5 as highest)
When user 42 clicks `Cancel bid` on bid 31 in this tab and confirms, and the POST answers 409 `{"error": "bid is not active"}`
Then My bids is reloaded first, and once that reload has finished the red error line shows `bid is not active` and stays shown
And the cancel notice is empty, bid 31 shows Status `cancelled` with no `Cancel bid` button, and the hint reads `Minimum next bid: 110` when the Auction ID field holds 7
And the stored standing of auction 7 is not cleared by this tab, the outbid banner logic runs on the reload as on any load, and no banner for auction 7 is shown

### S6 Network failure or unexpected answer while cancelling

Given My bids shows bid 31 on auction 7 as active and the server cannot be reached (in a test: `fetch` for the cancel POST rejects, as a browser's does when the server is down; any other way to make the server unreachable is fine too)
When user 42 clicks `Cancel bid` on bid 31 and confirms
Then the red error line shows `could not cancel bid 31` and the cancel notice is empty
And the list is not reloaded and the hint is not refreshed: bid 31 still shows Status `active` and its `Cancel bid` button, enabled again
And the same happens when the POST answers 500, 400, or 200 with a body that is not JSON

## Out of scope

- A "you are winning again" banner or any other message for a bid that becomes winning after a cancel.
- Keeping "Load more" rows across the reload that follows a cancel.
- Retrying a cancel automatically after a network failure.
- Any change to the outbid banner on a 404 or 409 cancel answer: the banner runs on that reload exactly as on any other load.

## Questions

- [B] (dev, iter 1) In S5 and the 404/409 row of the spec, the red error line must show `bid is not active` "after the reload", but the existing `load()` in day-11/webapp/index.html calls `showError("")` on every successful fetch. Should the error text be set after the reload finishes, or should `load()` stop clearing the error line when it follows a failed cancel? The reload and the error text would otherwise race. -> answered in ticket body (iter 1)
- [N] (dev, iter 1) On the 404/409 path the stored standing is not cleared, so the outbid banner logic can show a banner after the reload. For example, bid 31 was cancelled in another tab and the auction now reads outbid compared with the stored value. Is that accepted, or should the banner be suppressed on this path too? -> BA decision: the stored standing is not cleared and the banner logic runs unchanged on a 404/409 reload, because this request cancelled nothing (a too-late or not-found cancel leaves the auction as it was, so any change is a real outbid), and a cancel made in another tab already cleared the shared `localStorage` entry there, so it shows no banner (S5).
- [N] (dev, iter 1) While a cancel POST is in flight, should the `Cancel bid` button be disabled, or can a second click send a second POST? The second POST would get 409 `bid is not active` and put an error line over the success notice. -> answered in ticket body (iter 1)
- [N] (dev, iter 1) If the user edits the Auction ID field while the cancel POST is in flight, should the hint refresh use the value at the moment the answer arrives? The spec says "at that moment", so I would read the field when the response arrives. -> answered in ticket body (iter 1)
- [N] (dev, iter 1) In S1, if bid 61 is cancelled and the reload with page size 2 returns different first 2 rows than before, is that fine? I assume so, because the reload always starts from the first page. -> answered in ticket body (iter 1)
- [B] (dev, iter 2) S1 says a cancelled row has an "empty Standing", but the existing page writes `-` for a null standing, and for `winning` it writes `Winning`, not `winning`. Should the Standing cell of a cancelled row stay `-`, or become empty? Should the active row's cell read `Winning` as it does today? -> BA decision: keep the page's existing Standing rendering, `-` for a cancelled bid and `Winning` for a winning one (S1, S3 and the rules above the scenarios), because the spec only changes the page by the Cancel column and the cancel notice, and "empty" meant "no standing" (`standing` null), not a new cell format.
- [B] (dev, iter 2) The ticket gives the order as notice and clear stored standing, then reload, then error line. It doesn't say when the hint refresh runs. Does it run before the reload, after the reload has finished, or concurrently? Does it also run when the reload fails? -> BA decision: the hint refresh is step 4, after the reload has finished and after the 404 or 409 error line is written, and it also runs when the reload fails or is superseded, because the hint must match the auction after the cancel whatever happened to the list, and running it last keeps one fixed order to test.
- [N] (dev, iter 2) The existing `load()` has no try/catch, so a network failure on the reload fetch throws. Should the cancel flow catch that, still write the cancel error last, and go on to the hint refresh, as "if the reload itself fails" implies? -> answered in ticket body (iter 2)
- [N] (dev, iter 2) The spec only re-enables the `Cancel bid` button after a network failure. If the answer is a 400, a 500, or a body that isn't JSON, the error line shows `could not cancel bid <id>`. Should the button be enabled again, as it is for a network failure? Is the list reloaded in that case? -> answered in ticket body (iter 2)
- [N] (dev, iter 2) The reload says to "wait for it to finish", but `load()` starts `checkOutbid()` without awaiting it. Should "finished" cover only the list fetch and render, or also the banner check? If it covers the banner check, `load()` or `checkOutbid()` has to return a promise. -> BA decision: "finished" covers the list fetch and the table render only; the banner check is not awaited, because the banner never writes the red error line or the hint, so waiting for it changes nothing the bidder sees.
- [N] (dev, iter 2) If another `load()` (Reload, Place bid, or a second cancel) supersedes the cancel's reload through `loadSeq`, the cancel's reload returns early. Should the 404 or 409 error line still be written once that early return happens? -> BA decision: yes, the error line and the hint refresh still run once the superseded reload returns, and a newer load may later clear the error line as any load does, because the bidder should be told why the cancel failed and the newer load is the bidder's own later action.
- [N] (dev, iter 2) On a 200, which auction id is used to clear the stored standing: `auction_id` from the response body, or the one from the row? The ticket text assumes they are the same. -> BA decision: `auction_id` from the 200 response body, because it is the server's record of the cancelled bid and the cancel notice already uses it.
- [N] (dev, iter 2) In S6, "the server cannot be reached" is tested how? Should the test make `fetch` reject, or is any unreachable-server mechanism fine? -> answered in ticket body (iter 2)
