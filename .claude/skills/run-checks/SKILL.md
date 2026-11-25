---
name: run-checks
description: Runs every Recapz quality check (backend ruff, format, mypy, pytest; frontend prettier, eslint, typecheck, vitest, build) and summarizes failures. Use before committing or opening a pull request.
---

# Run checks

Run the checks that CI runs, stop at nothing, then summarize.

Backend, from `backend/`:

```
uv sync
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest
```

Integration tests need PostgreSQL: start it with `docker compose up -d db` from the
repository root first. Without it they are skipped, which is fine for a quick run but
not before a pull request.

Frontend, from `frontend/`:

```
npm install
npm run format:check
npm run lint
npm run typecheck
npm run test
npm run build
```

Report a table with one row per check: check, result (pass / fail / skipped), the first
error line when it failed. If a format check fails, run `uv run ruff format .` or
`npm run format` and say so. Do not change tests to make them pass.
