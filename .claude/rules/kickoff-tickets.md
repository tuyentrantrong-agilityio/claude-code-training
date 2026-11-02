---
paths:
  - "intent/**"
  - "scripts/lint_tickets.py"
---

# Kickoff ticket format

`scripts/lint_tickets.py` enforces this file. If you change one, change both.
(Tickets in `day-12/` predate the kickoff and follow `tickets.md` instead.)

## File

`intent/<folder>/tickets/T-NN-<slug>.md`: `NN` is two digits, `<slug>` is 2 to 5 kebab-case words.

## Shape

```markdown
# T-01 Show the time left on each auction

Status: draft
Spec: [Auctions](../spec.md#behaviour)

## Story

As a bidder
I want to ...
So that ...

## Scenarios

### S1 Bid placed before the end

Given auction 7 ends at 2026-12-01 18:00 UTC and its highest bid is 100
When user 42 bids 120 at 17:59
Then the API returns 201 and the bid is listed as winning

### S2 ...

## Out of scope

- ...

## Questions

- [B] (qa, iter 0) What happens when ... ? -> answered in ticket body (iter 1)
- [N] (dev, iter 1) Should the list ... ? -> BA decision: newest first, because ...
```

## Rules

- `Status:` is `draft` or `ready`. Only the BA sets `ready`, and only when no blocking
  question is open **and** the latest Dev round raised no `[B]`. Answering a Dev `[B]`
  keeps the ticket draft for one more Dev round: only a fresh read shows the guess is gone.
- `Dev rounds: <n>` (0-3) is added under `Status:` by `/kickoff` at the first Dev round.
  `Issue: #<n>` is added at the `promote` stage. Agents do not edit these two lines.
- The story has all three lines: `As a`, `I want`, `So that`.
- 1 to 6 scenarios, numbered `S1`, `S2`, ... Each has at least one `Given`, `When` and
  `Then` line (`And` lines are fine). Over 6 means split the ticket.
- Every `Then` is observable: an API status and body, a page text, a stored row.
  "Works correctly" is not a Then. Use concrete data (users, amounts, times).
- Out of scope has at least one line. Write `- Nothing excluded.` only if true.
- No `TBD`, `TODO` or `???`. Plain ASCII: write `->`, never an arrow character.
- Use `CONTEXT.md` terms. A new term goes into `CONTEXT.md` first (BA).

## Questions

One line per question: `- [B|N] (<source>, iter <n>) <question>`

- `[B]` blocking: a dev would have to guess and could guess wrong. `[N]` non-blocking.
- `<source>` is `ba`, `qa` or `dev`. BA and QA questions use `iter 0`; Dev questions use
  the Dev round (1-3).
- A question is open until its line ends with ` -> ` and one of:
  - `answered in ticket body (iter <n>)`: the body now answers it.
  - `client: <answer>`: the client answered (also put the answer into the body).
  - `BA decision: <choice>, because <reason>.`
  - `out of scope` (also add it to Out of scope).
- Never delete a question line; the scorecard counts the history.
- `## Questions` with no questions holds `- None yet.`
