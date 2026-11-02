# Claude Code automation in this repo

Project settings live in `settings.json`. Hooks run on events, skills are
tasks Claude follows on request. Run all tests with
`python .claude/skills/run-tests/run_tests.py`.

## Hooks (`.claude/hooks`)

| Event | Script | What it does |
|---|---|---|
| SessionStart | session_status.py | Adds branch, ahead/behind `origin/practice`, dirty file count and the main rules to the context; warns when on main or practice |
| UserPromptSubmit | git_reminder.py | When the prompt mentions commit, push, merge, tag, branch or MR, adds the git rules from CLAUDE.md |
| PreToolUse (Bash, PowerShell) | block_forbidden.py | Blocks force push, push to main or practice, `--no-verify`, `rm -rf` and bypasses of them |
| PreToolUse (Write, Edit) | block_secrets.py | Blocks `.env` files, `__pycache__`, and content that looks like a token or private key |
| PostToolUse (Write, Edit) | post_edit_check.py | Reports non-ASCII characters in the edited file; runs the tests of the day folder when a Python file there changed |

Tests: `python .claude/hooks/test_block_forbidden.py` and
`python .claude/hooks/test_hooks_extra.py`. The hooks are guardrails against
mistakes, not a sandbox.

## Skills (`.claude/skills`)

| Skill | Use |
|---|---|
| fix-ticket | Fix one ticket from branch to merge request |
| run-tests | Run every unittest suite and print one summary table |
| review-checklist | Check a branch against the CLAUDE.md rules before a merge request |
| evidence | Start the app, drive it in Chrome through MCP, save screenshots and publish the run |

The slash command `/mr-description` is in `.claude/commands`.
