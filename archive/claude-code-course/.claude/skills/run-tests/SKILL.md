---
name: run-tests
description: Run all unittest suites in this training repo (every day-NN folder with tests, plus the hook tests) and report one summary. Use when asked to run the tests, check that everything passes, or verify a change.
argument-hint: "[day-NN ...]"
allowed-tools: Bash(python .claude/skills/run-tests/run_tests.py:*)
---

Run the test suites and report the result honestly.

1. Run `python .claude/skills/run-tests/run_tests.py $ARGUMENTS` from the repo root.
   With no argument it runs every day folder that has a `tests` directory and
   the tests in `.claude/hooks`. With `day-02 day-11` it runs only those.
2. Show the summary table to the user as printed: one row per suite with the
   number of tests, OK or FAILED, and the time.
3. If a suite fails, quote the failure lines from the output and name the file.
   Do not edit a test to make it pass; fix the code unless the test is wrong,
   and say so if the test is wrong.
4. If the user wants the output kept as evidence, add `--save <path>` and
   tell them where the file is.

Never report a suite as passing without having run it in this turn.
