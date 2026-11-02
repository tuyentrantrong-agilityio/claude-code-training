---
description: Write a pull request description for the current branch against practice
allowed-tools: Bash(git log:*) Bash(git diff:*)
---

Commits on this branch:

!`git log --oneline origin/practice..HEAD`

Files changed:

!`git diff --stat origin/practice...HEAD`

Full diff:

!`git diff origin/practice...HEAD`

Write a pull request description for this branch in English, plain ASCII, with
three short sections: What (the change in one or two sentences), Why (the
ticket or problem it solves), and How tested (the exact test command and result;
if you have not run the tests, say so instead of guessing). Do not credit AI or
Claude as an author (no Co-Authored-By, no "Generated with ..."); naming Claude Code
as the subject is fine. Output only the description, ready to paste.
$ARGUMENTS
