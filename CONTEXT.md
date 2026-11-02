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
- **Page size / limit**: how many bids one page returns, 1 to 100.
- **Cursor**: the opaque `next_cursor` string that asks for the page after the current one.

## Work

- **Ticket**: one piece of work with a story, Given/When/Then acceptance criteria and open questions (format in `.claude/rules/tickets.md`).
- **Spec**: the agreed behaviour for one feature, which its tickets link to.
- **Intake**: the BA's first pass over a client brief: requirements, assumptions, open questions.
- **Test matrix**: QA's table of test cases derived from the acceptance criteria.
- **Open question**: something a ticket does not decide yet; it blocks work until answered.
- **Decision**: an answer recorded in the ticket, with who took it (dev, BA) and why.
- **Merge request (MR)**: the only way code reaches `practice`; `main` only receives `practice` for a release.
- **Release**: `practice` merged into `main` and tagged `vX.Y.Z`.
- **Evidence**: proof a result is real (test output, screenshots, artifact), produced by Claude while running the tools, never by hand.
