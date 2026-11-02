# Context

Glossary for this repo. Terms only: how things are built lives in
`docs/baseline.md`, the specs and `CLAUDE.md`. Add a term here before a ticket
or spec relies on it.

## Product

- **Auction**: something people bid on, known only by its `auction_id`. It exists once it has a bid.
- **Bid**: an offer of an integer `amount` by one user on one auction, at a time `created_at` (epoch ms).
- **Bidder**: a user who places bids. The web UI is always bidder `42`.
- **Active bid**: a bid with status `active`. Only active bids count for the highest bid.
- **Highest bid**: the active bid with the largest amount on an auction; ties go to the earliest, then the lowest id.
- **Standing**: `winning` (the bid is the highest bid), `outbid` (active but beaten) or `null` (not active).
- **Outbid banner**: the line "You were outbid on auction N" shown when an auction that was winning at the last page load is outbid now.
- **My bids**: the paged list of the current user's bids, newest first.
- **Minimum step**: how much a new bid must add to the highest bid: 10 while the highest amount is under 1000, 50 when it is 1000 or more. Fixed, the same on every auction.
- **Minimum next bid**: the lowest amount a new bid on an auction may have: highest bid amount plus the minimum step, or 1 when the auction has no active bid.
- **Minimum bid hint**: the grey line under the Amount field of the bid form that shows the minimum next bid for the auction typed in Auction ID.
- **Cancel (a bid)**: the bidder's own action that sets one of their active bids to status `cancelled`. The bid stays in My bids; it no longer counts for the highest bid. No undo.
- **Cancelled bid**: a bid with status `cancelled`. Listed in My bids with standing `null`; ignored for the highest bid and the minimum next bid.
- **Cancel window**: the 5 minutes (300000 ms, inclusive) after a bid's `created_at` during which its owner may cancel it.
- **Cancel notice**: the line on the My bids page that confirms a cancel: "Bid N on auction M cancelled."
- **Page size / limit**: how many bids one page returns, 1 to 100.
- **Cursor**: the opaque `next_cursor` string that asks for the page after the current one.

## Work

- **Ticket**: one piece of work with a story, Given/When/Then acceptance criteria and open questions (format in `.claude/rules/tickets.md`).
- **Spec**: the agreed behaviour for one feature, which its tickets link to.
- **Intake**: the BA's first pass over a client brief: requirements, assumptions, open questions.
- **Test matrix**: QA's table of test cases derived from the acceptance criteria.
- **Open question**: something a ticket does not decide yet; it blocks work until answered.
- **Decision**: an answer recorded in the ticket, with who took it (dev, BA) and why.
- **Pull request (PR)**: the only way code reaches `practice`; `main` only receives `practice` for a release.
  Merge requests `!1` to `!27` are the same flow on the old GitLab home.
- **CI check**: the GitHub Actions run on a PR; a PR is merged only when it is green.
- **Release**: `practice` merged into `main` and tagged `vX.Y.Z`.
- **Evidence**: proof a result is real (test output, screenshots, artifact), produced by Claude while running the tools, never by hand.

## Kickoff

- **Kickoff**: one run of the planning pipeline for one feature, in one `intent/` folder.
- **Lead / client**: the agent playing the person who wants the feature. Briefs vaguely on purpose.
- **Brief**: the client's first, deliberately vague description of the feature (`brief.md`).
- **Client truth**: the client's private list of what they really want. Hidden until the reveal.
- **BA decision**: an answer the BA chose when the client said "you decide", with a one-line reason.
- **Ticket pack**: all tickets of one feature, plus `spec.md`.
- **Dev round**: fresh Dev agents read each ticket cold and list the questions they would need answered.
- **Iteration**: one Dev round over a ticket. At most 3 per ticket.
- **Blocking question** `[B]`: a dev would have to guess, and could guess wrong.
- **Non-blocking question** `[N]`: nice to know; a dev could build correctly without it.
- **Ready ticket**: a ticket whose latest iteration has no open blocking question.
- **Gate**: a stop where the user approves (`approve gate N`) or sends questions back. Gates 1, 2 and 3.
- **Reveal**: the last stage: the client truth is shown and BA recall is scored.
- **BA recall**: client requirements the ticket pack covered, out of all of them.
