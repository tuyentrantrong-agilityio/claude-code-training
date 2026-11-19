# Playbook: shipping a feature with Claude Code

How a feature goes from a vague client request to a release in this repo, which part
Claude does, which part the human decides, and what checks it on the way. Every step
names the command and the file that enforces it. The worked example is the minimum
raise feature (`intent/2026-11-02-minimum-raise/`, issues #3 to #5, PRs #6 to #13).

Report page: https://claude.ai/artifact/2zuRg4DiTsHufMDFFjScFd (opens only for people it
is shared with). This file is the record; the page shows the same content.

## The flow

| Step | Command | Claude does | The human decides | Enforced by |
|---|---|---|---|---|
| 1. Kickoff | `/kickoff` (one stage per call) | Lead writes a vague brief and hidden client notes; BA writes intake, spec and tickets; QA writes the test matrix; fresh Dev agents read each ticket cold | `approve gate 1`, `2`, `3` (questions, ticket pack, promote to issues) | `record_approval.py` (only the typed phrase counts), `path_guard.py` (each role sees only its files), `gate_guard.py` (no issue before Gate 3), `lint_on_stop.py`, `scripts/lint_tickets.py` |
| 2. Reveal | `/kickoff` | Compares the hidden client notes with the tickets in `recall.md` and scores the BA | Corrects any verdict | `scripts/score_kickoff.py` (scores come from the script, not an agent) |
| 3. Build | one ticket, one `feat/` branch | Writes the tests from the matrix first, then the code; proves each new test fails on the old code | Says "ok push", merges | `post_edit_check.py` (ASCII, tests after each edit), `.claude/rules/tests.md` |
| 4. Evidence | `/evidence` | Starts the app with demo data, drives Chrome, saves screenshots, test logs and a report page into `evidence/T-NN/` | Shares the report page | `scripts/check_matrix.py` in CI: every planned test exists, the README shows every screenshot |
| 5. Review | `/review-pr <n>` | Checks out the head in a worktree, runs the checks there, a read-only `reviewer` agent writes findings; fixes go to a `fix/` PR | Which findings to fix, when to stop | `scripts/review_findings.py`, `path_guard.py` (reviewer reads, never writes) |
| 6. Push and PR | `gh pr create --base practice` | Commits in the repo format, pushes a branch, watches CI | Merges with a green CI | `pre_push_check.py` (no push while `check_branch.py` fails), `block_forbidden.py` (no push to main or practice, no force, no `--no-verify`), branch protection, CI |
| 7. Release | `/release <version>` | Notes from `scripts/release_notes.py`, practice into main, tag, GitHub release | Merges both PRs, approves the tag | `.claude/skills/release`, every GitHub write waits for a yes |

## What the minimum raise feature showed

- Kickoff: 3 tickets, 2 ready at the first Dev round, T-03 at the second; 5 blocking
  questions from Devs and 1 from QA; the BA caught the planted contradiction (flat 5 vs
  10/50 tiers) and recalled 8 of 8 client requirements, both hidden ones included.
- Build: 3 PRs, every test written from a matrix row; the matrix now has 53 rows, each
  pointing at a test that exists.
- Evidence: 9 screenshots taken by Claude in Chrome, test logs, two report pages.
- Review: the reviewer found 2 real bugs in merged T-03 code (a 5000-digit id dropped
  the connection; HEAD and OPTIONS gave 501). Three review rounds on the fix went from
  2 major to 1 major to only minor findings.
- Mistakes turned into checks: see `docs/retro.md` (for example the push that went out
  while `check_branch.py` failed is now blocked by a hook).

## Rules of thumb

- Claude drafts, checks and flags; a human approves gates, merges and releases.
- A lesson that only lives in a note is forgotten: put it in a hook, a script in CI,
  or a rule that loads with the files it covers.
- Proof lives in the repo. Report pages are for sharing; the evidence folder must
  stand on its own.
- Scores and checks come from scripts, never from an agent's opinion of its own work.
- A new hook is not trusted until it has blocked something on a safe target.

## Limits

- One fixed user (42) in the web UI; other bidders are seeded by scripts.
- Page JavaScript is tested in Node with a fake DOM; layout only in screenshots.
- Two day 15 retro items are still open: standing uses one query per bid, and the
  outbid banner looks at the first 100 bids only.
