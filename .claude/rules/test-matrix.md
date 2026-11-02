---
paths:
  - "intent/**"
  - "scripts/lint_tickets.py"
  - "scripts/check_matrix.py"
---

# Test matrix format

`intent/<folder>/test-matrix.md`, written by the QA agent. `scripts/lint_tickets.py` checks coverage.
After the build, `scripts/check_matrix.py` checks that each planned test exists.

## Table

One row per test case:

| ID | Ticket | Scenario | Type | Preconditions | Input | Expected | Planned test |
|---|---|---|---|---|---|---|---|
| M-001 | T-01 | S1 | happy | Auction 7, highest bid 100 by user 5 | User 42 posts amount 120 | 201, bid listed as winning | `day-02/tests/test_bids.py::test_higher_bid_wins` |

- **ID**: `M-NNN`, unique, in order.
- **Scenario**: `S<n>` from the ticket, or `edge` for a case no scenario covers yet.
- **Type**: `happy`, `edge` or `negative`.
- **Expected**: observable, same rule as a ticket's Then.
- **Planned test**: `<day folder>/tests/<file>.py::test_<name>`. Names only until the build;
  once the ticket is built the function must exist, and a renamed test updates its row.

## Rules

- Every scenario of every ticket has at least one row.
- Every ticket has at least one `negative` row.
- QA derives edge cases: amount boundaries (1, equal to the highest, 2^63-1), ties on
  amount and time, a bidder outbidding themselves, non-active bids, empty lists,
  paging limits (1, 100, 101) and cursors, two bids at the same moment.
- If the ticket does not say what should happen in an edge case, QA does not guess:
  QA adds a `[B] (qa, iter 0)` question to that ticket and writes `blocked by question`
  in Expected.
