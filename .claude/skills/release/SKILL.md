---
name: release
description: Cut a release of practice into main with release notes, a tag and a GitHub release. Use only when the user asks for a release (for example "/release v0.2.0").
argument-hint: "<version, e.g. v0.2.0>"
disable-model-invocation: true
---

Release $ARGUMENTS. `main` only receives `practice` for a release (CLAUDE.md). Every
GitHub write below (push, pull request, tag, release) needs the user's yes first;
the user merges both pull requests. Stop and report if a step fails.

## 1. Check practice is releasable

- `git fetch origin --tags`. Nothing to release if `git log <newest tag>..origin/practice --merges`
  is empty.
- The last CI run on practice is green: `gh run list --branch practice --limit 1`.
- Every kickoff in the range is clean: `python scripts/lint_tickets.py` and
  `python scripts/check_matrix.py` on each `intent/<folder>/` the notes list.
- Version: a `feat` in the range raises the minor number (v0.1.0 -> v0.2.0); only
  `fix`, `test`, `docs` or `chore` raise the patch number. Say which and why.

## 2. Notes on a release branch

- `git checkout -b docs/release-<version> origin/practice`, then
  `python scripts/release_notes.py <version> --out docs/releases/<version>.md`.
- Read the notes. Add at most a short "Highlights" paragraph at the top in plain
  words; never edit the generated lists by hand (fix the script or the PR title instead).
- Commit `docs: add release notes for <version>`, push, `gh pr create --base practice`,
  wait for CI. The user merges.

## 3. Practice into main

- `gh pr create --base main --head practice --title "release: <version>"` with the notes
  file as the body. Wait for CI. The user merges.

## 4. Tag and GitHub release

- `git fetch origin`, then tag the merge commit on main:
  `git tag -a <version> origin/main -m "Release <version>"` and `git push origin <version>`.
- `gh release create <version> --title <version> --notes-file docs/releases/<version>.md`.

## 5. Report

The version, the two pull requests, the tag commit, the release URL and the notes'
counts (merged changes, kickoffs). Point to the evidence folders the notes list.
