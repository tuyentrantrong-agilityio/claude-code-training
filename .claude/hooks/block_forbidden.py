"""PreToolUse hook for Bash: block commands that CLAUDE.md forbids.

Reads the hook input as JSON on stdin. Exit code 2 blocks the command and
sends the message on stderr back to Claude; exit code 0 lets it run.
"""

import json
import re
import sys

RULES = [
    (r"\bgit\s+push\b.*(\s--force\b|\s--force-with-lease\b|\s-[a-zA-Z]*f\b)",
     "force push is forbidden"),
    (r"\bgit\s+push\b.*\s(\S+:)?(main|practice)\b",
     "push directly to main or practice is forbidden; push a feature branch and open a merge request"),
    (r"\s--no-verify\b",
     "skipping hooks with --no-verify is forbidden"),
    (r"\brm\s+(-[a-zA-Z]*r[a-zA-Z]*f|-[a-zA-Z]*f[a-zA-Z]*r)\b",
     "rm -rf is forbidden; delete specific files instead"),
    (r"(?i)\bRemove-Item\b(?=.*\s-Recurse\b)(?=.*\s-Force\b)",
     "Remove-Item -Recurse -Force is forbidden; delete specific files instead"),
]


def strip_quoted(command):
    # Text inside quotes (commit messages, MR descriptions) is not a command.
    return re.sub(r"\"[^\"]*\"|'[^']*'", '""', command)


def check(command):
    # Check each chained command on its own, so "git push x; gh pr create --base main"
    # is not read as a push to main.
    for part in re.split(r"&&|\|\||[;|\n]", strip_quoted(command)):
        for pattern, reason in RULES:
            if re.search(pattern, part):
                return reason
    return None


def main():
    data = json.load(sys.stdin)
    command = data.get("tool_input", {}).get("command", "")
    reason = check(command)
    if reason:
        print(f"Blocked by .claude/hooks/block_forbidden.py: {reason}", file=sys.stderr)
        sys.exit(2)
    sys.exit(0)


if __name__ == "__main__":
    main()
