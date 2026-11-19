---
name: review-checklist
description: Check the current branch against the CLAUDE.md rules (commit message format, no AI mentions, ASCII only, no generated or secret files, tests pass) before opening a pull request. Use when asked to review or prepare a branch for a pull request.
argument-hint: "[base branch, default origin/practice]"
allowed-tools: Bash(python .claude/skills/review-checklist/check_branch.py:*) Bash(python .claude/skills/run-tests/run_tests.py:*) Bash(git fetch:*) Bash(git diff:*) Bash(git log:*)
---

Review the current branch before it becomes a pull request.

1. Run `git fetch origin`, then
   `python .claude/skills/review-checklist/check_branch.py $ARGUMENTS`.
   It checks, for the commits and diff against the base:
   - every commit subject is `<type>: <short description>` in lowercase, with no
     trailing period, and nothing mentions AI or Claude;
   - no `__pycache__`, `.pyc` or `.env` file is part of the diff;
   - no added line contains a non-ASCII character.
2. Run `python .claude/skills/run-tests/run_tests.py` and include the table.
3. Read `git diff origin/practice...HEAD` yourself and list, in plain English:
   - changes outside the scope of the branch name or ticket;
   - tests that were edited instead of the code;
   - new behaviour without a new test;
   - anything that needs a decision from the user.
4. Report as a short checklist: PASS or FAIL per check, then the findings from
   step 3 ordered by risk. Do not fix anything or push; propose fixes and let
   the user decide. A commit that is already pushed cannot be rewritten.
