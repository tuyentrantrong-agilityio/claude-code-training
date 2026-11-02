---
name: write-ticket
description: Writes or revises one kickoff ticket (story, Given/When/Then scenarios, out of scope, questions) so a developer can build it without blocking questions. Use when writing intent/<folder>/tickets/T-NN-*.md, or when the BA agent writes its ticket pack.
---

# Write a ticket

The format is in `.claude/rules/kickoff-tickets.md`; `scripts/lint_tickets.py` checks
it. This skill is about content that survives a cold read.

## Slice

- One ticket = one thing a bidder can do or see, end to end (data, API, page).
  Never "the table", "the API" and "the page" as three tickets.
- Order tickets so each builds on the last. T-01 is the thinnest useful slice.
- Over 6 scenarios: split by bidder outcome, not by layer.

## The zero-questions test

Before saving, read the ticket as a developer who only has the ticket, `spec.md` and
`docs/baseline.md`. For each scenario try to write the first failing test. Every
guess means the ticket is not done. The usual guesses:

| Guess | Make it explicit with |
|---|---|
| Valid inputs | Exact limits: amounts, lengths, allowed values, required or optional |
| What the bidder sees | The text, the list, the order, the empty state |
| Errors | Which input fails, the status code and message, what is kept |
| Time | Time zone, the exact moment something changes, past and future times |
| Ties and races | Equal amounts, same timestamp, two bids at once |
| Existing data | What happens to bids placed before the change, cancelled bids |
| Repeats | Doing the same action twice |
| Edges of the feature | Out of scope lines for the obvious next asks |

## Scenarios

- Concrete data: `Given auction 7 has a highest bid of 100 by user 5` beats `Given an auction`.
- One behaviour per scenario. The Then is observable: status code and body, page
  text, stored row.
- At least one unhappy path per ticket.
- If a client answer or a BA decision drove a scenario, state the outcome plainly;
  the reason lives in `intake.md`.

## Questions

- At `pack`: carry over anything still open as a `[B] (ba, iter 0)` line, never silently.
- At `dev-round`: answer by editing the body, then append ` -> ...` to the line.
  Never delete question lines.
