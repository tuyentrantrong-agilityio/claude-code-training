# Skill proof

Produced by `python scripts/skill_proof.py`: the command behind each skill is run
and its real output is shown, cut to the last 12 lines.

## run-tests: all suites, one summary

- Command: `python .claude/skills/run-tests/run_tests.py`
- Exit code: 0
- Output (end):

```
day-02                                      42 tests  OK        0.6s
day-04                                      11 tests  OK        0.1s
day-11                                     119 tests  OK       41.8s
tests (kickoff harness)                     63 tests  OK        4.7s
.claude/hooks/test_block_forbidden.py       11 tests  OK        0.6s
.claude/hooks/test_hooks_extra.py           25 tests  OK        0.3s
.claude/skills/review-checklist/test_check_branch.py    10 tests  OK        0.1s
total                                      281 tests  OK
```

## review-checklist: branch against the CLAUDE.md rules

- Command: `python .claude/skills/review-checklist/check_branch.py origin/practice`
- Exit code: 0
- Output (end):

```
[PASS] commit messages
[PASS] no pycache, .env or .pyc files
[PASS] no non-ASCII in added lines
Run the tests too: python .claude/skills/run-tests/run_tests.py
```

## write-ticket / test-matrix: ticket lint on the cancel bid kickoff

- Command: `python scripts/lint_tickets.py intent/2026-11-02-cancel-bid`
- Exit code: 0
- Output (end):

```
OK: intent\2026-11-02-cancel-bid
```

## test-matrix: every matrix row has its real test

- Command: `python scripts/check_matrix.py intent/2026-11-02-cancel-bid`
- Exit code: 0
- Output (end):

```
T-01: 20/20 rows have their test
T-02: 14/14 rows have their test
T-03: 16/16 rows have their test
T-04: 14/14 rows have their test
OK: intent\2026-11-02-cancel-bid
```

## release: notes generated for the range v0.2.0..v0.3.0

- Command: `python scripts/release_notes.py v0.3.0 --since v0.2.0 --to v0.3.0`
- Exit code: 0
- Output (end):

```
- T-01 Cancel a recent bid from My bids: issue #24, built, evidence in `evidence/T-01/`
- T-02 Limit cancels to five minutes: issue #25, built, evidence in `evidence/T-02/`
- T-03 Recalculate the auction after a cancel: issue #26, built, evidence in `evidence/T-03/`
- T-04 Keep the page in step after a cancel: issue #27, built, evidence in `evidence/T-04/`

Scorecard:

- Ready at round 1: 3/4 (75%)
- Contradiction flagged by the BA: yes
- BA recall: 8/8 (100%) (partial counts as half)
- Hidden requirements recall: 2/2 (100%)
- Missed: none
```

## Where the skills were used

| Skill | Trace in the repo |
|---|---|
| kickoff | intent/2026-11-02-cancel-bid/ (state, gates, scorecard, recall) |
| write-ticket, test-matrix | intent/2026-11-02-cancel-bid/tickets/ and test-matrix.md |
| review-pr | PRs #28 to #32: findings fixed in follow-up commits, see each PR |
| evidence | intent/2026-11-02-cancel-bid/evidence/T-01 to T-04 |
| release | docs/releases/v0.3.0.md, PRs #34 and #35, tag v0.3.0 |
| run-tests, review-checklist | run before every push (the pre_push_check hook runs check_branch) |
| fix-ticket | not used yet in this repo: no record exists, so none is claimed |
