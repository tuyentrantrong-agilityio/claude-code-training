# MCP in this repo

Three MCP sources are used or configured. Claude runs every flow; the user only gives the
command. Evidence is saved in the repo, next to the flow it proves.

| MCP | Where it is set up | Used for | Evidence in the repo |
|---|---|---|---|
| Claude in Chrome | Browser extension (not in `.mcp.json`) | Drive the web app and take screenshots | [day-15](../day-15/evidence/README.md), [minimum raise](../intent/2026-11-02-minimum-raise/evidence/README.md) |
| GitHub | `.mcp.json` (needs `GITHUB_PERSONAL_ACCESS_TOKEN` in the environment) | Create the kickoff issues at the `promote` stage | None yet (the issues #3 to #5 are the only trace) |
| Playwright | `.mcp.json` (`npx @playwright/mcp`, version not pinned) | A second browser driver for the web app | None yet: configured, never run end to end |

Do not read the last two rows as done: only Claude in Chrome has a recorded run.

## Flow 1: Claude in Chrome (done, recorded)

Command: `/evidence` ([guide](../.claude/skills/evidence/SKILL.md)). Claude, in order:

1. Saves the test output with `run_tests.py --save`.
2. Starts the web app with demo data on port 8010 (`seed_server.py`).
3. Loads the Chrome tools, opens a new tab, clears localStorage: first load shows no banner.
4. Sets page size 10 and reloads: Winning, Outbid and `-` appear in the Standing column.
5. Posts a bid below the minimum: the page shows the red line (the failing case, like a 422).
6. Posts a valid bid: the list is read back and shows the new bid as Winning.
7. Saves every screenshot, writes the evidence README with the images inline, publishes the report page.

The failing case (step 5) and the read-back (step 6) are the same checks a Swagger run
with 422 and a list call would give.

## Flow 2: GitHub MCP (configured, not yet recorded)

Command: `/kickoff` at the `promote` stage, after the user types `approve gate 3`.
Claude creates one issue per ready ticket, adds `Issue: #n` to the ticket and logs it in
`state.md`. `gate_guard.py` blocks any issue before Gate 3. To record a run: save the
created issue numbers and the tool calls in `intent/<folder>/evidence/promote.md`.

## Flow 3: Playwright MCP (configured, not yet recorded)

Planned run, to be done with the Playwright tools loaded: open the web app on port 8010,
post a bid below the minimum (expect the 409 error line), post a valid bid, read the list
back, and save the snapshots under `intent/<folder>/evidence/`. Until that run exists this
row stays "none yet"; pin the version in `.mcp.json` when it is recorded.

## Rules

- Evidence is made by Claude with the tools, never by hand; screenshots are shown inline in
  the README so GitHub renders them when a report link does not open.
- Say what was staged (seeded second user, localStorage set by the javascript tool).
- Hook behaviour is recorded in [hook-proof.md](hook-proof.md).
