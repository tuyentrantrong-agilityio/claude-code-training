# Recapz build plan (T04, part 1)

How the backlog in `backlog.md` is built: order, milestones, and the pull-request sized
work items for the next phases. No dates are set here; progress is reported daily.

Inputs: `02-requirements.md` (scope), `03-architecture.md` (stack), `04-data-model.md`
(schema), `05-api-contract.md` (API). These were merged in PR #40 and are the baseline;
changes to them go through a pull request that updates the doc first.

## 1. Principles

- Plan before code: every work item starts with a short plan (Claude Code plan mode) and
  ends with tests and a pull request.
- Guardrails first: CI, hooks and the PR checklist exist before feature code.
- Offline before live: upload, transcript, recap and Ask work end to end before the
  calendar, the notetaker or any live feature.
- One work item = one branch = one pull request into `recapz-practice`, small enough to
  review in one sitting.
- UI follows the prototype; any difference is written in the PR description.
- No paid AI call in CI; providers are faked behind the adapter interfaces.

## 2. Milestones

| Milestone | Contains | Exit check |
|---|---|---|
| M0 Planning | T01, T02, T03, T31, T32, T04 | Docs merged into `recapz-practice` |
| M1 Foundation | T05, T06, T07, T37, T08, T09, T10, T45 (setup part) | Sign in with an invited Google account and see the empty app shell; CI green |
| M2 Offline MVP | T34, T33, T35, T11, T12, T42, T13, T14, T36, T15, T16, T17 | Upload a recording, get transcript and recap, ask a question with a citation |
| M3 Hardening | T38, T39, T40, T45 (full suites), T30 (first pass) | Staging deploy, isolation tests, E2E for the MVP flows |
| M4 Calendar and notetaker | T18, T19, T20, T21, T41, T44 | Bot joins a test Meet, the recording becomes a report, live transcript works |
| M5 Organize, share, admin | T22, T23, T24, T25, T26, T27, T43 | Features match the prototype screens |
| M6 Stretch | T28, T29 | Only if time allows |

The AI provider decision (open in `03-architecture.md`) must be made before T12. Until
then the pipeline is built against fake adapters, so M1 and the start of M2 are not
blocked.

## 3. Work items for M1 (Foundation)

| ID | Branch | Work item | Backlog | Depends on |
|---|---|---|---|---|
| F-01 | `feat/project-skeleton` | Backend (FastAPI app factory, settings, `/api/v1/health`), frontend (Vite, React, TypeScript, Tailwind, router), `docker-compose.yml` with PostgreSQL + pgvector, `.env.example`, root README run steps | T05 | - |
| F-02 | `chore/quality-gates` | ruff, mypy, pytest; eslint, prettier, tsc, vitest; pre-commit hooks; GitHub Actions CI (backend and frontend jobs, Postgres service); PR template with UI-parity checklist | T06, T45 | F-01 |
| F-03 | `chore/claude-code-setup` | CLAUDE.md commands section, reviewer and UI-parity subagents, a run-checks skill, plan-mode workflow note | T07 | F-02 |
| F-04 | `feat/db-foundation` | Async SQLAlchemy, Alembic for `public` and per-organization schemas, `search_path` per request and per job, org create script, tests against Postgres | T08 | F-02 |
| F-05 | `feat/job-runner` | `jobs` table, worker loop with `FOR UPDATE SKIP LOCKED`, retries with backoff, a sample job, tests | T08, T35 (base) | F-04 |
| F-06 | `feat/app-shell` | Layout and sidebar like the prototype, design tokens, empty state and toast components, placeholder routes | T09 | F-01 |
| F-07 | `docs/google-cloud-setup` | GCP project, OAuth consent, scopes, redirect URIs, test users; steps in the Build Guide | T37 | - (done by hand) |
| F-08 | `feat/auth-google` | OAuth sign-in, invites, sessions, roles, `/me`, CSRF; sign-in page and "not invited" state | T10 | F-04, F-06, F-07 |
| F-09 | `feat/seed-and-admin-invites` | Seed script (org, owner, invite), minimal Admin invites and members API and page | T10, T26 (MVP part) | F-08 |

## 4. Work items for M2 (Offline MVP), first cut

| ID | Work item | Backlog |
|---|---|---|
| P-01 | Provider interfaces and fake adapters, usage recording | T34 |
| P-02 | Storage interface, upload endpoint, ffmpeg decode job | T33, T11 |
| P-03 | Meetings list page with tabs, search and live stage updates (SSE) | T11 |
| P-04 | Batch transcription job with the chosen provider, speakers, language | T12, T42 |
| P-05 | Recap job (LLM JSON, timestamp validation, idempotent replace) | T13 |
| P-06 | Report page: Recap, Transcript, People tabs, audio player with chapters | T14 |
| P-07 | Search chunks, full-text and pgvector index job | T36 |
| P-08 | Ask API with hybrid retrieval, streaming, validated citations | T15 |
| P-09 | Ask page and the report side panel | T15 |
| P-10 | Follow-ups API and page, sidebar badge | T16 |
| P-11 | Home page | T17 |
| P-12 | Retry and failure handling across stages, Incomplete state | T35 |

These are refined (split or merged) when M1 is done.

## 5. Definition of done (every work item)

- Plan written in the PR description (what, why, how it was tested).
- Tests added or updated; CI green.
- UI items: screenshot next to the matching prototype screen, differences listed.
- Docs updated when behaviour, setup or the API changes.
- No secrets, no AI credit lines, ASCII only in code and docs.

## 6. Risks

| Risk | Mitigation |
|---|---|
| Vietnamese transcription quality is poor | Compare providers on our own samples before T12; keep the adapter swappable |
| Per-organization schemas complicate migrations | Build and test the migration runner in F-04 before any feature table |
| Google OAuth and Meet need real accounts | Do F-07 early; keep a dedicated test account |
| The notetaker (T20) is fragile | Start it only after M2; log and snapshot every step |
| AI cost during development | Fakes in CI, usage recorded per call from P-01, small sample files |
