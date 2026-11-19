"""PostToolUse hook for Write and Edit: check the file that was just written.

1. Plain ASCII only (CLAUDE.md): report non-ASCII characters with line numbers.
2. If a Python file inside a day-NN folder changed and that folder has tests,
   run that folder's unittest suite and report a failure.

Exit code 2 sends the message on stderr to Claude (the write already happened).
Exit code 0 means nothing to report.
"""

import json
import os
import re
import subprocess
import sys
import unicodedata

TEXT_EXTENSIONS = {".py", ".md", ".html", ".json", ".txt", ".yml", ".yaml", ".toml", ".cfg", ".ini"}
SKIP_PARTS = ("/.git/", "/.claude/worktrees/", "/__pycache__/")
DAY_FILE = re.compile(r"(?:^|/)(day-\d+)/")


def non_ascii_report(text, limit=5):
    """Return lines like 'line 3: U+2014 EM DASH' for the first non-ASCII chars."""
    found = []
    for number, line in enumerate(text.splitlines(), 1):
        for char in line:
            if ord(char) > 127:
                found.append(f"line {number}: U+{ord(char):04X} {unicodedata.name(char, 'UNKNOWN')}")
                if len(found) >= limit:
                    return found
    return found


def day_folder(path):
    """Return the day-NN folder path that owns this file and has tests, else None."""
    norm = path.replace("\\", "/")
    match = DAY_FILE.search(norm)
    if not match:
        return None
    folder = norm[: match.end(1)]
    return folder if os.path.isdir(os.path.join(folder, "tests")) else None


def run_day_tests(folder, timeout=90):
    """Run the folder's unittest suite. Return None if it passes, else the output tail."""
    try:
        done = subprocess.run(
            [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-t", "."],
            cwd=folder, capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return f"tests in {folder} did not finish within {timeout} seconds"
    if done.returncode == 0:
        return None
    return "\n".join((done.stderr or done.stdout).strip().splitlines()[-15:])


def check(path):
    norm = path.replace("\\", "/")
    if any(part in norm for part in SKIP_PARTS) or not os.path.isfile(path):
        return None
    if os.path.splitext(path)[1].lower() not in TEXT_EXTENSIONS:
        return None
    with open(path, encoding="utf-8", errors="replace") as f:
        text = f.read()
    report = non_ascii_report(text)
    if report:
        return f"{path} has non-ASCII characters (CLAUDE.md requires plain ASCII):\n" + "\n".join(report)
    folder = day_folder(path) if path.endswith(".py") else None
    if folder:
        failure = run_day_tests(folder)
        if failure:
            return f"tests in {folder} fail after editing {path}:\n{failure}"
    return None


def main():
    try:
        data = json.load(sys.stdin)
        path = str((data.get("tool_input") or {}).get("file_path", ""))
    except ValueError:
        return 0
    message = check(path) if path else None
    if message:
        print(message, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
