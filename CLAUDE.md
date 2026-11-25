# CLAUDE.md

Recapz practice: a meeting notetaker (record, transcribe, recap, ask with citations)
rebuilt from the Recapz design prototype. FastAPI backend, React frontend, PostgreSQL.

## Commands

- Database: `docker compose up -d db`
- Backend (from `backend/`): `uv sync`, `uv run fastapi dev app/main.py`,
  checks `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy`, `uv run pytest`
- Frontend (from `frontend/`): `npm install`, `npm run dev`, checks `npm run format:check`,
  `npm run lint`, `npm run typecheck`, `npm run test`, `npm run build`
- All checks at once: the `run-checks` skill
- Review a branch: the `reviewer` subagent; compare a screen with the prototype: the
  `ui-parity` subagent

## Sources of truth

- Prototype: https://claude.ai/artifact/5dS2kuzsPwZsnydb4Aj2Ji. UI and behaviour must
  match it unless a decision doc says otherwise.
- `docs/recapz/`: inventory (01), requirements (02), architecture (03), data model (04),
  API contract (05), build plan (06), build guide (07), backlog.
- GitHub issues T01 to T45 track the work; `06-build-plan.md` lists the work items.
- `archive/claude-code-course/`: old course work, read only, never edit or run it.

## Workflow per work item

1. Read the issue, its row in `06-build-plan.md` and the docs it depends on.
2. Write a plan first (plan mode) and wait for approval before code.
3. Branch from `recapz-practice`: `feat/`, `fix/`, `chore/` or `docs/`.
4. Code with tests; run the `run-checks` skill until green.
5. Run the `reviewer` subagent on the diff; for UI work also `ui-parity`.
6. `gh pr create --base recapz-practice`, fill the PR template, link the issue
   (`Closes #N`). The user merges.

## Conventions

- Commit messages: `<type>: <short description>`, lowercase, imperative, no trailing
  period. Types: `feat`, `fix`, `docs`, `test`, `refactor`, `chore`.
- No AI credit in commits and pull request descriptions: no `Co-Authored-By` trailer,
  no "Generated with/by ..." line.
- English in code and docs. Plain ASCII only: no emoji, em dashes, curly quotes or
  arrows.
- Backend: routers thin, logic in `app/services`, every org query inside the tenant
  scope, times inside a recording in milliseconds (`*_ms`), errors in the format of
  `05-api-contract.md`.
- Frontend: TypeScript strict, TanStack Query for server state, components named after
  the prototype.
- Tests never call paid AI providers; use the fake adapters.

## Model use

- Planning and review: the strongest model. Coding: a mid model. Mechanical edits
  (renames, formatting, issue updates): the smallest model.

## Never do

- Never push directly to `main`, `practice` or `recapz-practice`; never force push.
- Never commit secrets or `.env` files.
- Never change a test only to make it pass; fix the code unless the test is wrong.
- Never put unconfirmed decisions in docs as if they were agreed; mark them as proposals.
