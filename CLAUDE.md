# CLAUDE.md

Recapz practice: a meeting notetaker (record, transcribe, recap, ask with citations)
rebuilt from the Recapz design prototype. Currently in Phase 0 (planning); there is no
application code yet.

## Sources of truth

- Prototype: https://claude.ai/artifact/5dS2kuzsPwZsnydb4Aj2Ji. UI and behaviour must
  match it unless a decision doc says otherwise.
- `docs/recapz/01-feature-inventory.md`: screens, states and entities from the prototype.
- `docs/recapz/backlog.md`: the approved task list (T01 to T45).
- `archive/claude-code-course/`: old course work, read only, never edit or run it.

## Conventions

- Commit messages: `<type>: <short description>`, lowercase, imperative, no trailing
  period. Types: `feat`, `fix`, `docs`, `test`, `refactor`, `chore`.
- No AI credit in commits and pull request descriptions: no `Co-Authored-By` trailer,
  no "Generated with/by ..." line.
- English in code and docs. Plain ASCII only: no emoji, em dashes, curly quotes or
  arrows.
- Planning docs live in `docs/recapz/`, numbered in the order they are written.

## Repository

- GitHub: `tuyentrantrong-agilityio/claude-code-training` (remote `origin`). Use `gh`.
- Base branch for this practice: `recapz-practice`. Work on a `feat/`, `fix/` or
  `docs/` branch from it, then `gh pr create --base recapz-practice`. The user merges.
- Windows (PowerShell and Git Bash).

## Never do

- Never push directly to `main`, `practice` or `recapz-practice`.
- Never force push or rewrite history that is already pushed.
- Never commit secrets or `.env` files.
- Never put unconfirmed decisions in docs as if they were agreed; mark them as proposals.
