# claude-code-training

A small auction platform built during a 15-day Claude Code training, and the
Claude Code setup used to build it: rules, hooks, skills and a merge request flow
where Claude drafts and checks, and a human decides every merge.

## The product

Bidders place bids on auctions. A bid must beat the current highest bid, and each
bid in "My bids" shows whether it is winning or outbid. The full behaviour is in
[`docs/baseline.md`](docs/baseline.md), the terms in [`CONTEXT.md`](CONTEXT.md).

| Part | Where | What it does |
|---|---|---|
| Bids store | `day-02/auction/bids.py` | Place bids atomically, list my bids with cursor paging and standing |
| Web app | `day-11/webapp/` | JSON API and the "My bids" page with an outbid banner |
| Bid standing feature | `day-12/` | Client brief, intake, spec, test matrix and tickets T1 to T4 |
| Release | tag `v0.1.0` on `main` | First release, merged from `practice` |

```
cd day-11 && python -m webapp.server          # http://127.0.0.1:8000
python .claude/skills/run-tests/run_tests.py   # every test suite, one summary
```

## How work flows

| Step | Who | Output |
|---|---|---|
| Brief and intake | Client, BA | `00-client-brief.md`, `01-intake.md` with open questions |
| Spec and tickets | BA | `02-spec.md`, `ticket-T*.md` with Given/When/Then |
| Test matrix | QA | `03-test-matrix.md` |
| Build | Dev with Claude, plan mode first | One branch and one MR per ticket into `practice` |
| Review | `/code-review`, `review-checklist`, browser check | Findings fixed in their own MR |
| Evidence | Claude through `/evidence` | Screenshots, test output and an artifact page |
| Release | Human merges `practice` into `main` | Tag `vX.Y.Z` |

## How Claude Code is used

| Feature | Where |
|---|---|
| Project memory | `CLAUDE.md` (short, always loaded), `CONTEXT.md`, `docs/baseline.md` |
| Rules loaded on demand | `.claude/rules/tickets.md`, `.claude/rules/tests.md` |
| Hooks | `.claude/hooks/`: session status, git rule reminder, command guard, secret guard, ASCII and test check after edits |
| Skills | `.claude/skills/`: `fix-ticket`, `run-tests`, `review-checklist`, `evidence` |
| Slash command | `.claude/commands/mr-description.md` |
| MCP | Claude in Chrome drives the web app for evidence; `.mcp.json` declares Playwright |
| Loop | `.claude/loop.md`: what `/loop` checks on the `practice` branch |

Details of every hook and skill are in [`.claude/README.md`](.claude/README.md).

## Repository rules

Branches `fix/`, `feat/` or `docs/` from `practice`, one merge request each, no
direct pushes to `main` or `practice`, stdlib only, plain ASCII. See `CLAUDE.md`.
