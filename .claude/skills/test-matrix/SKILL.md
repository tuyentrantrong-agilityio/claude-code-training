---
name: test-matrix
description: Drafts a kickoff test matrix (test-matrix.md) from tickets' Given/When/Then scenarios, adds derived edge cases, and raises a blocking question where a ticket leaves behaviour undefined. Use when writing or updating test-matrix.md in an intent folder, or when the QA agent runs.
---

# Draft a test matrix

The table format and coverage rules are in `.claude/rules/test-matrix.md`;
`scripts/lint_tickets.py` checks coverage.

## Steps

1. For each ticket in order, add one row per scenario (`happy` or `negative` as the
   scenario is), copying its Given into Preconditions, its When into Input and its
   Then into Expected, with concrete data.
2. Derive edge cases per ticket and add them as `edge` rows, linked to the scenario
   they extend, or `edge` in the Scenario column if none covers them. Keep only what
   applies:
   - Amounts: 1, equal to the highest bid, one more than the highest, 2^63-1, 0, negative.
   - Ties: equal amounts, equal `created_at`, order by id.
   - Status: `active` and non-active bids; a bidder outbidding themselves.
   - Lists: empty, one item, exactly a full page, `limit` 1, 100 and 101, a bad cursor.
   - Time: the exact boundary moment, past and future, time zone (UTC).
   - Concurrency: two equal bids at the same moment.
   - Repeats: the same request twice.
3. When the ticket and spec do not say what the result is, raise `[B] (qa, iter 0)`
   on the ticket and write `blocked by question` in Expected. One question per
   unknown, phrased so the answer is one sentence.
4. Name the planned test after the behaviour:
   `<day folder>/tests/test_<area>.py::test_<what_happens>`.

Keep the matrix to what the tickets promise. No cases for a ticket's Out of scope.
