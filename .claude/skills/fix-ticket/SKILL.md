---
name: fix-ticket
description: Fix one ticket from a day folder in this training repo, from branch to merge request. Use when asked to fix, implement or work on a ticket file such as day-04/ticket-1.md.
argument-hint: "[path to ticket file]"
disable-model-invocation: true
---

Fix the ticket in $ARGUMENTS by following these steps in order. Stop and report if a step fails.

## 1. Understand the ticket

- Read the ticket file and every file it names under Component.
- Read the failing test it names, if any, and run the day's suite to see the failure:
  `cd day-XX && python -m unittest discover -s tests -t . -v`
- Restate the expected behaviour in one sentence before changing code.

## 2. Branch

- Start from the latest practice: `git fetch origin`, then
  `git checkout -b <type>/<short-name> origin/practice`.
- Use `fix/` for bugs, `feat/` for new behaviour, `docs/` or `chore/` for the rest.
- Run `git branch --unset-upstream` so a plain `git push` cannot reach practice.

## 3. Change the code

- Make the smallest change that meets the ticket. Python stdlib only.
- Fix the code, not the tests. Add new tests for new behaviour; never edit an
  existing assertion to make it pass unless the ticket says the test is wrong.
- Plain ASCII and English only in code, comments and test names.

## 4. Verify

- Run the day's suite again; every test must pass.
- `git status` must list only files the ticket needs (no `__pycache__`).
- `git diff origin/practice` must not touch other day folders.

## 5. Commit and open the merge request

- One commit, message `<type>: <short description>`, lowercase, imperative,
  no trailing period, and no Co-Authored-By or any line about AI.
- Push and open the MR into practice with GitLab push options:

```
git push -u origin <branch> -o merge_request.create -o merge_request.target=practice -o "merge_request.title=<commit message>" -o "merge_request.description=<what changed, why, how it was tested>"
```

- Never push to main or practice directly, never force push, never merge.

## 6. Report

Reply with: the root cause in one line, the change, the test result
(number of tests and pass/fail), the commit hash and the MR URL from the push output.
