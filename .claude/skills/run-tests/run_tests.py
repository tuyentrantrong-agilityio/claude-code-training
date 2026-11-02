"""Run every unittest suite in the repo and print one summary table.

Usage: python .claude/skills/run-tests/run_tests.py [day-NN ...] [--save PATH]
With no day given it runs every day-NN folder that has a tests directory, the
kickoff harness tests in tests/, and the test_*.py files in .claude/hooks and
.claude/skills/*. Exit code is 1 if any suite fails.
"""

import glob
import os
import re
import subprocess
import sys
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
RAN = re.compile(r"Ran (\d+) tests? in")
SKIPPED = re.compile(r"skipped=(\d+)")


def parse_result(output, returncode):
    """Return (tests, status, skipped) from unittest output."""
    match = RAN.search(output)
    tests = int(match.group(1)) if match else 0
    skipped = SKIPPED.search(output)
    skipped = int(skipped.group(1)) if skipped else 0
    if returncode == 0:
        return tests, "OK", skipped
    return tests, "FAILED" if match else "ERROR", skipped


def run(cmd, cwd):
    start = time.time()
    done = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    output = (done.stdout or "") + (done.stderr or "")
    tests, status, skipped = parse_result(output, done.returncode)
    return tests, status, skipped, time.time() - start, output


def suites(days):
    found = []
    for folder in sorted(glob.glob(os.path.join(ROOT, "day-*"))):
        name = os.path.basename(folder)
        if os.path.isdir(os.path.join(folder, "tests")) and (not days or name in days):
            found.append((name, [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-t", "."], folder))
    if not days:
        if os.path.isdir(os.path.join(ROOT, "tests")):
            found.append(("tests (kickoff harness)", [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-t", "."], ROOT))
        for path in sorted(glob.glob(os.path.join(ROOT, ".claude", "hooks", "test_*.py"))
                           + glob.glob(os.path.join(ROOT, ".claude", "skills", "*", "test_*.py"))):
            name = os.path.relpath(path, ROOT).replace(os.sep, "/")
            found.append((name, [sys.executable, path], ROOT))
    return found


def main(argv):
    save = None
    if "--save" in argv:
        i = argv.index("--save")
        save = argv[i + 1]
        argv = argv[:i] + argv[i + 2:]
    rows, failures, total, total_skipped = [], [], 0, 0
    for name, cmd, cwd in suites(set(argv)):
        tests, status, skipped, seconds, output = run(cmd, cwd)
        total, total_skipped = total + tests, total_skipped + skipped
        row = f"{name:<40} {tests:>5} tests  {status:<7} {seconds:5.1f}s"
        rows.append(row + (f"  ({skipped} skipped)" if skipped else ""))
        if status != "OK":
            failures.append((name, "\n".join(output.strip().splitlines()[-15:])))
    if not rows:
        print("no test suites found")
        return 1
    report = "\n".join(rows)
    report += f"\n{'total':<40} {total:>5} tests  " + ("FAILED" if failures else "OK")
    report += f"  ({total_skipped} skipped)" if total_skipped else ""
    for name, tail in failures:
        report += f"\n\n--- {name} ---\n{tail}"
    print(report)
    if save:
        with open(save, "w", encoding="utf-8") as f:
            f.write(report + "\n")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
