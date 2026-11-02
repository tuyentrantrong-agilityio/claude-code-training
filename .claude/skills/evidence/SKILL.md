---
name: evidence
description: Capture proof that the web app works. Claude starts the app with demo data, drives it in Chrome through the Claude in Chrome MCP tools, saves the screenshots and test output into the repo, and publishes the run as an artifact. Use when asked for evidence, a screenshot, a demo run or proof of a result.
argument-hint: "[day-NN folder to save into, default day-15]"
disable-model-invocation: true
---

Produce evidence yourself. The user must not take screenshots or copy output by hand.

## 1. Prepare

- Pick the target folder from $ARGUMENTS (default `day-15`) and create `<folder>/evidence`.
- Save test output first: `python .claude/skills/run-tests/run_tests.py --save <folder>/evidence/tests.txt`.
- Start the app in the background:
  `python .claude/skills/evidence/seed_server.py 8010`. If the port is taken, use another one.
  Confirm it answers with `curl -s http://127.0.0.1:8010/api/bids`.

## 2. Drive the app in Chrome

Load the Chrome tools once with ToolSearch, then call `tabs_context_mcp`, open a
new tab and work there. Run these steps and take a screenshot with
`save_to_disk` after each one:

1. Clear localStorage with the javascript tool, open the page: no outbid banner.
2. Page size 10, Reload: Winning, Outbid and "-" are shown in the Standing column.
3. Bid 100 on auction 8 (highest is 300): the message "bid must be higher than 300".
4. Bid 400 on auction 8: new bid is Winning and the old own bid is Outbid.
5. Set localStorage `standing` to `{"7":"winning"}` and reload: the outbid banner.

Look at every screenshot before keeping it. If a result differs from the
expectation (for example a banner on a first visit), say so and clear the
state, never relabel the screenshot. Close the tab you opened when done.

## 3. Save and publish

- Copy the screenshots into `<folder>/evidence/` with names like
  `01-first-load-no-banner.jpg`, and write `<folder>/evidence/README.md` with a
  table of file and what it shows, plus the limits of the run.
- Publish an artifact page with the screenshots (as data URIs), what each step
  did, the tools used, the test output and the limits.
- Stop the background server.

## 4. Report

List the files saved, the artifact link, and the limits (one fixed UI user, the
competing bid seeded by the script, banner triggered through localStorage).
Do not commit or push unless the user asks.
