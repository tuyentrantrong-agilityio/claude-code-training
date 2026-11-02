# Claude Code automation in this repo

Project settings live in `settings.json`: permissions, the status line and the
hooks. Agents play the kickoff roles, skills are procedures Claude follows, rules
load on demand, hooks enforce what must never depend on Claude remembering.
Run all tests with `python .claude/skills/run-tests/run_tests.py`.

## Subagents (`.claude/agents`)

| Agent | Role | Tools | Model | Writes |
|---|---|---|---|---|
| lead | The client: vague brief, private truth, answers in character | Read, Write, Edit, Glob | sonnet | client truth, `brief.md`, answers in `intake.md` |
| ba | Intake, spec, ticket pack, Dev-round revisions | Read, Write, Edit, Glob, Grep | opus | `intake.md`, `spec.md`, `tickets/`, `CONTEXT.md` |
| qa | Test matrix and blocking questions on gaps | Read, Write, Edit, Glob, Grep | sonnet | `test-matrix.md`, questions in tickets |
| dev | Reads one ticket cold and lists what it would have to ask | Read, Glob, Grep | sonnet | nothing |
| reviewer | Reviews a change against its ticket, test matrix and repo rules (`/review-pr`) | Read, Glob, Grep | opus | nothing; replies with the findings, which `/review-pr` saves and checks |

What each role may read and write is enforced by `path_guard.py`, not only by its prompt.

## Hooks (`.claude/hooks`)

| Event | Script | What it does |
|---|---|---|
| SessionStart | session_status.py | Branch, ahead/behind `origin/practice`, dirty files, main rules; warns on main or practice |
| SessionStart, status line | load_state.py | Active kickoff, next stage and any waiting gate |
| UserPromptSubmit | git_reminder.py | Adds the git rules when the prompt is about commit, push, merge, tag, branch, MR or PR |
| UserPromptSubmit | record_approval.py | Turns the user's `approve gate N` into `approvals/gate-N.md`; nothing else counts as approval |
| PreToolUse (Bash, PowerShell) | block_forbidden.py | Blocks force push, push to main or practice, `--no-verify`, `rm -rf` and bypasses |
| PreToolUse (Write, Edit) | block_secrets.py | Blocks `.env` files, `__pycache__`, and content that looks like a token or key |
| PreToolUse (file tools, shell) | path_guard.py | Keeps each kickoff role and the reviewer inside its files; hides the client truth until the reveal; nobody writes approvals |
| PreToolUse (shell, MCP) | gate_guard.py | No issue (GitHub MCP, `gh issue create`, `gh api` POST, browser new-issue page) before Gate 3 |
| PostToolUse (Write, Edit) | post_edit_check.py | Reports non-ASCII characters; runs the day's tests when a Python file there changed |
| SubagentStop (ba, qa) | lint_on_stop.py | Keeps the BA or QA working once if `scripts/lint_tickets.py` fails on its files |
| Stop | notify_gate.py | Desktop notification when a kickoff gate waits for the user |

`permissions.deny` also blocks Write and Edit under `intent/*/approvals/`.
Tests: `tests/` (kickoff hooks and scripts), `.claude/hooks/test_block_forbidden.py`,
`.claude/hooks/test_hooks_extra.py`. The hooks are guardrails against mistakes, not a sandbox.

## Rules (`.claude/rules`)

Loaded only when Claude works on matching files, so `CLAUDE.md` stays short.

| Rule | Applies to |
|---|---|
| kickoff-tickets.md | `intent/**`, `scripts/lint_tickets.py` |
| test-matrix.md | `intent/**`, `scripts/lint_tickets.py` |
| tickets.md | `day-*/ticket*.md` and the planning files `day-*/0*-*.md` (before the kickoff harness) |
| tests.md | `day-*/tests/**` and `.claude/**/test_*.py` |

## Skills (`.claude/skills`)

| Skill | Use |
|---|---|
| kickoff | Run the feature kickoff one stage per call, stopping at the three gates |
| write-ticket | Write a ticket that passes the zero-questions test (BA) |
| test-matrix | Draft the test matrix with derived edge cases (QA) |
| fix-ticket | Fix one ticket from branch to pull request |
| run-tests | Run every unittest suite and print one summary table |
| review-checklist | Check a branch against the CLAUDE.md rules before a pull request |
| review-pr | Prepare `.review/<branch>/` (worktree of the head, diff, context, checks), run the reviewer agent, report findings |
| evidence | Start the app, drive it in Chrome through MCP, save screenshots and publish the run |
| release | Notes from `scripts/release_notes.py`, practice into main, tag and GitHub release (user-triggered) |

The slash command `/pr-description` is in `.claude/commands`.
CI: `.github/workflows/ci.yml` runs every suite and lints every kickoff folder on each PR.
