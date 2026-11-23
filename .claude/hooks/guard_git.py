"""PreToolUse hook: block risky git commands before Claude Code runs them.

Blocks: pushing to protected branches, force pushes, and commits whose message carries
an AI credit line. Exit code 2 tells Claude Code to block the call and show the reason.
"""

import json
import re
import sys

PROTECTED = ("main", "practice", "recapz-practice")
CREDIT = re.compile(r"co-authored-by|generated (with|by)", re.IGNORECASE)


def check(command: str) -> str | None:
    if re.search(r"\bgit\s+push\b", command):
        if re.search(r"(\s--force(-with-lease)?\b|\s-f\b)", command):
            return "Force push is not allowed."
        for branch in PROTECTED:
            if re.search(rf"(\s|:){re.escape(branch)}(\s|$)", command):
                return f"Do not push to {branch}; open a pull request instead."
    if re.search(r"\bgit\s+commit\b", command) and CREDIT.search(command):
        return "Commit messages must not contain AI credit lines."
    return None


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0
    command = str(payload.get("tool_input", {}).get("command", ""))
    reason = check(command)
    if reason:
        print(reason, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
