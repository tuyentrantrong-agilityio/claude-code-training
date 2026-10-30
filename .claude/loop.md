Check the training repo for new work on the practice branch. This repo is on a
self-managed GitLab, so use git only; there is no gh or glab.

1. Run `git fetch origin`.
2. Compare `practice` with `origin/practice` and list any new commits
   (`git log --oneline practice..origin/practice`).
3. If there are new commits, run the tests for each day folder that changed:
   `cd day-XX && python -m unittest discover -s tests -t . -v`.
4. Report in one or two lines: new commits (yes/no) and test result
   (pass/fail with the failing test names).

Do not commit, push, merge, or change any file. If nothing changed and the
last run was green, say so in one line.
