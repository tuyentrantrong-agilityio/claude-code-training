# MCP in this repo

Three MCP sources are used or configured. Claude runs every flow; the user only gives the
command. Evidence is saved in the repo, next to the flow it proves.

| MCP | Where it is set up | Used for | Evidence in the repo |
|---|---|---|---|
| Claude in Chrome | Browser extension (not in `.mcp.json`) | Drive the web app and take screenshots | [day-15](../day-15/evidence/README.md), [minimum raise](../intent/2026-11-02-minimum-raise/evidence/README.md) |
| GitHub | `.mcp.json` (needs `GITHUB_PERSONAL_ACCESS_TOKEN` in the environment) | Create the kickoff issues at the `promote` stage; read issues, pull requests and CI | Run on 2026-11-03: reads and two writes, see Flow 2 |
| Playwright | `.mcp.json` (`npx @playwright/mcp`, pinned to 0.0.84) | Kept for later: a clean, repeatable browser for tests that run in CI | None yet: configured, never run end to end |

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

## Flow 2: GitHub MCP (recorded)

Command: `/kickoff` at the `promote` stage, after the user types `approve gate 3`.
Claude creates one issue per ready ticket, adds `Issue: #n` to the ticket and logs it in
`state.md`. `gate_guard.py` blocks any issue before Gate 3.

Recorded run on 2026-11-03, after the token was set and the session restarted. Before the
token was set the server failed with `Authorization header is badly formatted` (the header
was an empty `Bearer `). The first four issues of kickoff 2 (#24 to #27) were created with
`gh` because the MCP server was not connected at that time. Claude, in order:

1. `get_me`: logged in as `tuyentrantrong-agilityio`, so the token works.
2. `list_issues` (state open, repo `claude-code-training`): 7 open issues, #24 to #27 of the
   cancel bid kickoff, each assigned to the user, plus #3 to #5 of the minimum raise kickoff.
   Read back as the check that the earlier `gh` run left the right issues.
3. `pull_request_read` with `get_check_runs` on PR #23: job `tests` completed with `success`.

4. `issue_write` (state closed, reason completed) on #24 and #5: both closed, after the user's
   yes. Their tickets were built and merged.
5. `issue_write` on #3 and #4 was denied by the permission classifier, which asked for the
   user's explicit rule. Claude did not work around it (no `gh` fallback); the user closes
   them, or adds an allow rule for `mcp__github__issue_write`.

Found by the run: issues #3 to #5 were still open although their tickets were built and
merged (PRs #7 to #9).

Not covered: creating an issue through the MCP. The failing case (a bad token) is the error
above, and the denial in step 5 is the permission check working.

## Flow 3: Playwright MCP (configured, not yet recorded)

Planned run, to be done with the Playwright tools loaded: open the web app on port 8010,
post a bid below the minimum (expect the 409 error line), post a valid bid, read the list
back, and save the snapshots under `intent/<folder>/evidence/`. Until that run exists this
row stays "none yet". Claude in Chrome already covers the evidence runs; Playwright is kept
for what Chrome cannot do: a clean browser with no sign-in, repeatable runs and CI.

## Rules

- Evidence is made by Claude with the tools, never by hand; screenshots are shown inline in
  the README so GitHub renders them when a report link does not open.
- Say what was staged (seeded second user, localStorage set by the javascript tool).
- Hook behaviour is recorded in [hook-proof.md](hook-proof.md).
