"""Check a reviewer's findings file against the format in .claude/agents/reviewer.md.

Usage: python scripts/review_findings.py .review/<branch>/findings.md

Prints one problem per line and exits 1 if there are any. Standard library only.
"""

import re
import sys
from pathlib import Path

FINDING = re.compile(r"^- \[(blocker|major|minor)\] (\S+?):(\d+) (.+) Rule: (.+)$")


def sections(text):
    out, name = {}, None
    for line in text.splitlines():
        if line.startswith("## "):
            name = line[3:].strip()
            out[name] = []
        elif name and line.strip():
            out[name].append(line.rstrip())
    return out


def check(text):
    problems = []
    if not text.startswith("# Review: "):
        problems.append("first line must be '# Review: <branch>'")
    if any(ord(c) > 127 for c in text):
        problems.append("plain ASCII only")
    parts = sections(text)
    findings = parts.get("Findings")
    if findings is None:
        problems.append("missing '## Findings'")
    elif findings != ["- None."]:
        for line in findings:
            if not FINDING.match(line):
                problems.append(
                    f"finding not in the form '- [blocker|major|minor] <file>:<line> <what> Rule: <source>': {line}"
                )
    if not parts.get("Checked"):
        problems.append("'## Checked' needs at least one line saying what was checked")
    return problems


def counts(text):
    found = [FINDING.match(line) for line in sections(text).get("Findings", [])]
    levels = [m.group(1) for m in found if m]
    return {level: levels.count(level) for level in ("blocker", "major", "minor")}


def main(argv):
    if len(argv) != 1:
        print("usage: python scripts/review_findings.py <findings.md>", file=sys.stderr)
        return 2
    path = Path(argv[0])
    if not path.is_file():
        print(f"{path}: missing", file=sys.stderr)
        return 1
    text = path.read_text(encoding="utf-8")
    problems = check(text)
    for p in problems:
        print(f"{path.name}: {p}")
    if not problems:
        c = counts(text)
        print(f"OK: {c['blocker']} blocker, {c['major']} major, {c['minor']} minor")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
