"""Check the current branch against the rules in CLAUDE.md before a pull request.

Usage: python .claude/skills/review-checklist/check_branch.py [base]
base defaults to origin/practice. Exit code is 1 if any check fails.
"""

import os
import re
import subprocess
import sys

COMMIT_FORMAT = re.compile(r"^(feat|fix|docs|test|refactor|chore): [a-z0-9](?:[^A-Z]*[^.A-Z\s])?$")
# Credit to an AI as an author is not allowed; naming the tool as the subject
# ("a playbook for shipping a feature with claude code") is fine.
AI_TOOL = r"(?:an? |the )?(?:ai|claude|chatgpt|gpt|copilot|llm|anthropic)\b"
ATTRIBUTION = re.compile(
    r"co-authored-by"
    r"|\bgenerated (?:with|by)\b"
    r"|\b(?:written|created|made|authored|produced|captured|drafted|assisted|done|coded) (?:by|with) " + AI_TOOL +
    r"|\bby " + AI_TOOL +
    r"|\b(?:ai|claude|llm|gpt)[- ](?:generated|written|assisted)\b"
    r"|noreply@anthropic\.com",
    re.IGNORECASE,
)
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
    if ATTRIBUTION.search(subject):
        return "subject credits AI or Claude as an author"
    return None


def check_body(body):
    if ATTRIBUTION.search(body):
        return "message credits AI or Claude as an author"
    return None


def known_commits(path=None):
    """Full shas of pushed commits excused from the message rules, from known_commits.txt."""
    path = path or os.path.join(os.path.dirname(os.path.abspath(__file__)), "known_commits.txt")
    try:
        with open(path, encoding="utf-8") as f:
            return {line.split()[0] for line in f if line.strip() and not line.startswith("#")}
    except OSError:
        return set()


def commit_problems(entries, excused):
    """'<sha> <subject>: <problem>' for each commit that breaks a rule and is not excused."""
    problems = []
    for entry in filter(str.strip, entries):
        sha, subject, body = (entry.strip("\n").split("\x1f") + ["", ""])[:3]
        issue = check_subject(subject) or check_body(body)
        if issue and sha not in excused:
            problems.append(f"{sha[:7]} {subject}: {issue}")
    return problems


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
    record("commit messages", commit_problems(commits, known_commits()))

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
