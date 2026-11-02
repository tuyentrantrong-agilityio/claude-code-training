# Retro: from lessons to checks

A lesson that only lives in a note or in Claude's memory gets forgotten on the next
busy day. Each lesson below is turned into something that runs on its own: a hook,
a script in CI, or a rule that loads with the files it covers.

## Rework after the mentor review (2026-11-02)

| What went wrong | Where it is enforced now |
|---|---|
| The repo was judged basic: hooks only on PreToolUse, simple skills, no shared MCP result | Hooks on 6 events (`.claude/README.md`); kickoff harness with 4 role agents and 3 gates; reviewer agent; release skill |
| Evidence was screenshots taken by hand | `/evidence` skill: Claude drives Chrome and saves screenshots, test logs and a report page |
| Evidence existed only behind a private report link | `scripts/check_matrix.py` in CI: a built ticket needs `evidence/T-NN/README.md` showing every screenshot inline |
| The matrix promised tests nobody checked for | `scripts/check_matrix.py` in CI: each row of a built ticket names a test function that exists |
| `check_branch.py` printed FAIL, the output went through `| grep`, the push went on and CI went red (PR #12) | `pre_push_check.py` hook: denies `git push` of a branch while `check_branch.py` fails |
| Tests asserted a status without the body, or compared two live answers (M-038, M-049, M-051) | `.claude/rules/tests.md`: assert the whole answer as literal values; the reviewer checks it |
| T-03 shipped with three endpoint bugs that passed every test | `/review-pr` with the `reviewer` agent before or after merge; findings kept in `evidence/T-NN/review.md` |
| Page JavaScript had no automated test | `day-11/tests/js/hint_harness.js` runs the page script in Node; `run_tests.py` shows skipped tests so a missing Node is visible |
| A subagent cannot write report files, so a stop hook checking the reviewer's file never fired | The reviewer replies; `/review-pr` saves the reply and checks it with `scripts/review_findings.py` |
| The kickoff skill let the BA mark a ticket ready right after answering a blocking question | Kickoff skill and BA agent: a ticket is ready only after a Dev round with no `[B]` (see the kickoff skill fix) |

## Day 15 retro items (`day-15/retro-issues.md`)

| Item | Status |
|---|---|
| 1. Standing uses one query per bid and no index | Open |
| 2. Outbid banner checks only the first 100 bids | Open |
| 3. JavaScript in `index.html` has no automated test | Closed for the minimum bid hint (Node harness); the banner logic is still untested |
| 4. Race test can hang without a barrier timeout | Closed: `threading.Barrier(20, timeout=10)`, as `.claude/rules/tests.md` asks |
