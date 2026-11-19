"""PreToolUse hook for Write and Edit: block secrets and generated files.

Exit code 2 blocks the write and sends the message on stderr back to Claude.
CLAUDE.md: never commit secrets, .env files or __pycache__.
"""

import json
import ntpath
import re
import sys

SECRET_PATTERNS = [
    (r"glpat-[A-Za-z0-9_-]{20}", "GitLab personal access token"),
    (r"gh[pousr]_[A-Za-z0-9]{36}", "GitHub token"),
    (r"AKIA[0-9A-Z]{16}", "AWS access key id"),
    (r"-----BEGIN [A-Z ]*PRIVATE KEY-----", "private key block"),
    (r"(?i)(password|passwd|secret|api[_-]?key|token)\s*=\s*['\"][^'\"\s]{12,}['\"]",
     "hard-coded credential assignment"),
]


def check_path(path):
    """Return a reason if writing to this path is forbidden, else None."""
    norm = path.replace("\\", "/")
    name = ntpath.basename(norm)
    if name == ".env" or (name.startswith(".env.") and name != ".env.example"):
        return "writing an .env file is forbidden (use .env.example without values)"
    if "/__pycache__/" in norm or name.endswith(".pyc"):
        return "generated files such as __pycache__ must not be written"
    return None


def check_content(text):
    """Return a reason if the text looks like it contains a secret, else None."""
    for pattern, label in SECRET_PATTERNS:
        if re.search(pattern, text):
            return f"content looks like a secret ({label})"
    return None


def check(data):
    inp = data.get("tool_input") or {}
    reason = check_path(str(inp.get("file_path", "")))
    if reason:
        return reason
    return check_content(str(inp.get("content", "")) + "\n" + str(inp.get("new_string", "")))


def main():
    try:
        data = json.load(sys.stdin)
    except ValueError:
        print("block_secrets: cannot read the hook input, blocking to be safe", file=sys.stderr)
        return 2
    reason = check(data)
    if reason:
        print(f"Blocked by block_secrets: {reason}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
