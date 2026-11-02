# CLAUDE.md

A small auction platform (bids, standing, a web UI) used as the practice product
for Claude Code training. Python stdlib only, no dependencies.

## Commands

- All tests: `python .claude/skills/run-tests/run_tests.py`
- One day's tests: `cd day-NN && python -m unittest discover -s tests -t . -v`
- Web app: `cd day-11 && python -m webapp.server` (http://127.0.0.1:8000)
- Demo data app on another port: `python .claude/skills/evidence/seed_server.py 8010`
- Feature kickoff: `/kickoff`; lint `python scripts/lint_tickets.py intent/<folder>`,
  score `python scripts/score_kickoff.py intent/<folder>`, matrix against real tests
  `python scripts/check_matrix.py intent/<folder>`
- Review a PR with the reviewer agent: `/review-pr <n>` (workspace in `.review/`, gitignored)
- Release notes: `python scripts/release_notes.py <version>`; a release: `/release <version>`

## Layout

- `docs/baseline.md`: what the app does today. Features are specified on top of it.
- `CONTEXT.md`: glossary. Use its terms; add a term before relying on it.
- `day-02/auction`: bids store (core). `day-11/webapp`: web UI and JSON API.
- `day-12`: planning documents and tickets for the bid standing feature (before the kickoff harness).
- `intent/<date>-<slug>/`: one folder per feature kickoff; `intent/CURRENT` names the active one.
- `.kickoff-private/`: the client agent's hidden notes, gitignored until the reveal.
- `scripts/`: ticket linter and kickoff scorecard. Tests for them and the kickoff hooks in `tests/`.
- `.claude/`: hooks, skills, rules and commands (map in `.claude/README.md`).
- Format rules load on demand: tickets in `.claude/rules/tickets.md`, tests in `.claude/rules/tests.md`.

## Conventions

- Commit messages: `<type>: <short description>`, lowercase, imperative, no trailing
  period. Types: `feat`, `fix`, `docs`, `test`, `refactor`, `chore`.
- No AI credit in commits and pull request descriptions: no `Co-Authored-By` trailer,
  no "Generated with/by ..." line, nothing like "by Claude" or "AI-generated". Naming
  the tool as the subject is fine ("playbook for shipping a feature with claude code").
  `check_branch.py` checks this; pushed commits that cannot be reworded are listed, with
  a reason, in `.claude/skills/review-checklist/known_commits.txt`.
- English everywhere in code. Plain ASCII only: no emoji, em dashes, curly quotes,
  arrows or bullet symbols. No lines saying code was AI-generated.
- Keep comments short and only where the code is not self-explanatory.
- Evidence (test output, screenshots, run reports) is produced by Claude with the
  tools (`/evidence`), never collected by hand.

## Repository

- GitHub: `tuyentrantrong-agilityio/claude-code-training` (remote `origin`). Use `gh`.
  The old home on GitLab (remote `gitlab`, MRs !1 to !27) is kept as an archive; do not push there.
- Work on a `fix/`, `feat/` or `docs/` branch from `origin/practice`, then
  `gh pr create --base practice`. A PR is merged by the user, only with a green CI check
  (`.github/workflows/ci.yml`). `main` only receives `practice` for a release.
- Windows (PowerShell and Git Bash).

## Never do

- Never push directly to `main` or `practice`.
- Never add third-party dependencies; stdlib only.
- Never change tests to make them pass; fix the code unless the test itself is wrong.
- Never force push, skip hooks, or rewrite history that is already pushed.
- Never commit secrets, `.env` files, or generated files such as `__pycache__`.
- Never commit or push unless asked to.
- Never write, edit or delete anything under `intent/*/approvals/`; only the user's
  `approve gate N` creates those files. "ok" or "looks good" is not an approval.
- Never read or quote the client truth before the kickoff's reveal stage, and never
  create GitHub issues for a kickoff before Gate 3 is approved.
