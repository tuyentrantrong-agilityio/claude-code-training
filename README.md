# claude-code-training

A small auction platform built during a 15-day Claude Code training, and the
Claude Code setup used to build it: rules, hooks, skills and a pull request flow
where Claude drafts and checks, and a human decides every merge.

## The product

Bidders place bids on auctions. A bid must beat the current highest bid by a minimum step, and each
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

## Run a feature kickoff

A client asks for a feature; four agents (client, BA, QA, Dev) turn the vague brief
into a ticket pack a developer can build without asking a single question. A human
approves every gate. Open the repo in Claude Code, then:

```text
/kickoff                 start, or advance one stage
approve gate 1           approve the stage Claude stopped at (1, 2 or 3)
```

| Stage | Who | Writes | Then |
|---|---|---|---|
| `brief` | lead | `.kickoff-private/client-truth.md`, `brief.md` | continue |
| `intake` | ba | `intake.md` (requirements, assumptions, open questions) | **Gate 1** |
| `answers` | lead | client answers in `intake.md` | continue |
| `pack` | ba, then qa | `spec.md`, `tickets/`, `test-matrix.md` | **Gate 2** |
| `dev-round` | dev per ticket, ba | questions in tickets, BA revisions, `scorecard.md` | **Gate 3** |
| `promote` | Claude | GitHub issues from ready tickets | continue |
| `reveal` | Claude | client truth into the folder, `recall.md`, final scorecard | done |

Scores come from `scripts/score_kickoff.py`, never from an agent's opinion. The
folder layout is in [`intent/README.md`](intent/README.md).

## How work flows

| Step | Who | Output |
|---|---|---|
| Kickoff | `/kickoff` with the lead, ba, qa and dev agents | `intent/<date>-<slug>/` ticket pack, scorecard |
| Build | Dev with Claude, plan mode first | One branch and one PR per ticket into `practice`, CI must be green |
| Review | `/code-review`, `review-checklist`, browser check | Findings fixed in their own PR |
| Evidence | Claude through `/evidence` | Screenshots, test output and an artifact page |
| Release | Human merges `practice` into `main` | Tag `vX.Y.Z` |

## How Claude Code is used

| Feature | Where |
|---|---|
| Project memory | `CLAUDE.md` (short, always loaded), `CONTEXT.md`, `docs/baseline.md` |
| Subagents | `.claude/agents/`: `lead`, `ba`, `qa`, `dev`, each with its own tools, model and file access |
| Rules loaded on demand | `.claude/rules/`: kickoff tickets, test matrix, day tickets, tests |
| Hooks | `.claude/hooks/`: kickoff state, gate approvals, role file access, issue guard, lint on subagent stop, gate notification, command and secret guards, ASCII and test check after edits |
| Skills | `.claude/skills/`: `kickoff`, `write-ticket`, `test-matrix`, `fix-ticket`, `run-tests`, `review-checklist`, `evidence` |
| Scripts | `scripts/lint_tickets.py`, `scripts/score_kickoff.py` (tests in `tests/`) |
| Status line | the kickoff stage and whether a gate is waiting |
| Slash command | `.claude/commands/pr-description.md` |
| MCP | `.mcp.json`: GitHub (issues at the kickoff `promote` stage) and Playwright; Claude in Chrome drives the web app for evidence |
| CI | `.github/workflows/ci.yml`: every test suite, kickoff lint and the CLAUDE.md commit check on each PR |
| Loop | `.claude/loop.md`: what `/loop` checks on the `practice` branch |

Details of every hook and skill are in [`.claude/README.md`](.claude/README.md).

## Repository rules

Branches `fix/`, `feat/` or `docs/` from `practice`, one pull request each, no
direct pushes to `main` or `practice`, stdlib only, plain ASCII. See `CLAUDE.md`.
