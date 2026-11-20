# Recapz build guide (T04, part 2)

How to work in this repository: layout, local setup, conventions, testing and the pull
request flow. Sections marked *(after F-01)* describe the setup that the first
foundation work item creates.

## 1. Repository layout (target)

```
backend/                 FastAPI app (Python, uv)
  app/
    api/v1/              routers, one module per area (meetings, ask, follow_ups, ...)
    core/                settings, logging, security, errors
    db/                  engine, session, tenant search_path, models
    jobs/                worker loop and job handlers
    providers/           STT, LLM, embedding, TTS interfaces and adapters (incl. fakes)
    services/            business logic, no FastAPI imports
  migrations/            Alembic: public/ and org/ version folders
  tests/                 unit/, integration/ (needs Postgres), fixtures/
frontend/                React app (Vite, TypeScript, Tailwind)
  src/
    app/                 router, layout, providers
    components/          shared UI (avatar, stamp, switch, modal, empty state, toast)
    features/            one folder per screen (home, meetings, report, ask, ...)
    lib/                 api client, sse helper, formatters
  tests/
docs/recapz/             planning docs (numbered)
docker-compose.yml       PostgreSQL with pgvector for local development
.env.example             every variable the apps read
.github/                 CI workflow, PR template
```

## 2. Local setup *(after F-01)*

Prerequisites: Git, Docker Desktop, Python 3.12 with `uv`, Node.js 22 with npm, ffmpeg
(needed from P-02).

```
copy .env.example .env          # PowerShell; or: cp .env.example .env
docker compose up -d db
cd backend
uv sync
uv run alembic upgrade head     # after F-04
uv run fastapi dev app/main.py  # http://127.0.0.1:8000/api/v1/health
cd ../frontend
npm install
npm run dev                     # http://127.0.0.1:5173
```

The worker (after F-05): `cd backend && uv run python -m app.jobs.worker`.

## 3. Configuration

- All settings come from environment variables, read in `app/core/settings.py`.
- `.env` is never committed; `.env.example` lists every variable with a safe default or
  an empty value.
- Provider keys, OAuth secrets and the encryption key exist only in `.env` and in the
  CI or deploy secrets.

## 4. Conventions

### General
- English in code, comments and docs. Plain ASCII only.
- Commit messages: `<type>: <short description>`, lowercase, imperative, no trailing
  period. Types: `feat`, `fix`, `docs`, `test`, `refactor`, `chore`.
- No AI credit lines in commits or pull requests.

### Backend
- Format and lint with ruff; type-check with mypy (strict for `app/`).
- Routers stay thin: validate input, call a service, map errors to the format in
  `05-api-contract.md`.
- Every query runs inside the request or job tenant scope; never build a schema name
  from user input.
- Times inside a recording are integer milliseconds (`*_ms`).

### Frontend
- TypeScript strict, eslint and prettier.
- Server state with TanStack Query; no global store until it is needed.
- Components follow the prototype names and states (empty, processing, incomplete).

## 5. Testing

| Level | Tool | Runs in CI | Notes |
|---|---|---|---|
| Backend unit | pytest | yes | no database, no network |
| Backend integration | pytest + PostgreSQL | yes (service container) | real migrations, tenant isolation |
| Frontend unit | vitest + Testing Library | yes | components and hooks |
| E2E | Playwright | from M3 | main flows against a seeded stack |

- AI providers are replaced by fakes in tests; recorded fixtures live in
  `backend/tests/fixtures/`.
- A bug fix comes with a test that fails before the fix.
- Never change a test only to make it pass; fix the code unless the test is wrong.

## 6. Branches and pull requests

1. Update `recapz-practice`, then create `feat/...`, `fix/...`, `chore/...` or
   `docs/...` from it.
2. Plan the change first (Claude Code plan mode) and keep the plan in the PR description.
3. Run the checks locally (hooks run them on commit and push).
4. Open the PR into `recapz-practice` with `gh pr create --base recapz-practice`.
5. Fill the PR template, including the UI-parity checklist for UI work.
6. The owner merges after a green CI and a review.

Never push directly to `recapz-practice`, `practice` or `main`; never force push a
shared branch.

## 7. Working with Claude Code

- Model use: a stronger model for planning and review, a faster model for coding, the
  smallest model for mechanical edits.
- Start each work item from its row in `06-build-plan.md` and the docs it depends on.
- Ask for a plan first; approve it before code is written.
- Keep CLAUDE.md short: commands, layout, conventions, never-do rules. Longer rules go
  into files that are loaded on demand.
- The reviewer subagent (F-03) reviews each PR diff against this guide; the UI-parity
  subagent compares screens with the prototype.

## 8. Google Cloud setup *(F-07, filled in when done)*

Placeholder for the OAuth client, consent screen, scopes, redirect URIs and test users.
