"""Check the current branch against the rules in CLAUDE.md before a pull request.

Usage: python .claude/skills/review-checklist/check_branch.py [base]
base defaults to origin/practice. Exit code is 1 if any check fails.
"""

import re
import subprocess
import sys

COMMIT_FORMAT = re.compile(r"^(feat|fix|docs|test|refactor|chore): [a-z0-9](?:[^A-Z]*[^.A-Z\s])?$")
AI_MENTION = re.compile(r"co-authored-by|generated with|\bclaude\b|\banthropic\b|\bai\b", re.IGNORECASE)
FORBIDDEN_PATH = re.compile(r"(^|/)(__pycache__/|\.env($|\.(?!example$))|[^/]*\.pyc$)")


def git(*args):
    done = subprocess.run(["git", *args], capture_output=True, text=True, encoding="utf-8", errors="replace")
    if done.returncode != 0:
        raise RuntimeError(done.stderr.strip() or "git failed")
    return done.stdout


def check_subject(subject):
    """Return a problem for a commit subject, or None."""
    if not COMMIT_FORMAT.match(subject):
        return "subject is not '<type>: <short description>' in lowercase without a trailing period"
    if AI_MENTION.search(subject):
        return "subject mentions AI or Claude"
    return None


def check_body(body):
    if AI_MENTION.search(body):
        return "message mentions AI or Claude"
    return None


def forbidden_paths(paths):
    return [p for p in paths if FORBIDDEN_PATH.search(p)]


def added_non_ascii(diff):
    """Return 'file: char' for added lines that contain non-ASCII characters."""
    problems, current = [], ""
    for line in diff.splitlines():
        if line.startswith("+++ "):
            current = line[6:] if line.startswith("+++ b/") else line[4:]
        elif line.startswith("+") and any(ord(c) > 127 for c in line):
            bad = next(c for c in line if ord(c) > 127)
            problems.append(f"{current}: U+{ord(bad):04X}")
    return problems


def main(argv):
    base = argv[0] if argv else "origin/practice"
    results = []

    def record(name, problems):
        results.append((name, problems))

    commits = git("log", "--no-merges", "--format=%H%x1f%s%x1f%b%x1e", f"{base}..HEAD").split("\x1e")
    problems = []
    for entry in filter(str.strip, commits):
        sha, subject, body = (entry.strip("\n").split("\x1f") + ["", ""])[:3]
        issue = check_subject(subject) or check_body(body)
        if issue:
            problems.append(f"{sha[:7]} {subject}: {issue}")
    record("commit messages", problems)

    paths = git("diff", "--name-only", f"{base}...HEAD").splitlines()
    record("no pycache, .env or .pyc files", [f"{p}" for p in forbidden_paths(paths)])
    record("no non-ASCII in added lines", added_non_ascii(git("diff", "-U0", f"{base}...HEAD")))

    failed = False
    for name, problems in results:
        print(f"[{'FAIL' if problems else 'PASS'}] {name}")
        for p in problems:
            print(f"       {p}")
        failed = failed or bool(problems)
    print("Run the tests too: python .claude/skills/run-tests/run_tests.py")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
