---
name: review-pr
description: Review a branch or pull request with the reviewer agent against its kickoff ticket, the test matrix and the repo rules, then show the findings. Use when asked to review a PR, a branch, or a ticket's implementation before merge.
argument-hint: "[PR number, or nothing for the current branch]"
---

The reviewer agent (`.claude/agents/reviewer.md`) does the review. You prepare its
input, start it, check its output and report. You do not review the code yourself.

## 1. Prepare

- With a PR number: `gh pr view <n> --json headRefName,baseRefName,body`. The issue is
  the `Closes #N` in the body. Fetch and use `--base origin/<base> --head origin/<head>`.
- Without one: the current branch against `origin/practice`; the issue is the `Closes #N`
  of its open PR if there is one (`gh pr view --json body`), else none.
- Run `python scripts/review_context.py --base <base> --head <head> [--issue N]`.
  It prints the folder `.review/<branch>/` with `context.md` and `diff.patch`.

## 2. Review

Spawn a **fresh** `reviewer` with `Folder: .review/<branch>/.` Pass the path only, never
the diff or your own opinion of it. The reviewer is read-only (subagents cannot write
report files) and replies with the findings document.

Save its reply, unchanged, as `.review/<branch>/findings.md`, then run
`python scripts/review_findings.py .review/<branch>/findings.md`. If it fails, send the
problems to the same reviewer once and save its new reply; then stop and say so.
Never edit a finding yourself: the findings are the reviewer's.

## 3. Report

Show the counts line, every blocker and major finding as written, and how many minor
findings there are. Open `findings.md` for the rest.

Do not post anything to GitHub on your own. If the user asks, post `findings.md` as one
PR comment with `gh pr comment <n> --body-file .review/<branch>/findings.md`.
Fixing a finding is a separate change on the ticket's branch, made after the user agrees.
