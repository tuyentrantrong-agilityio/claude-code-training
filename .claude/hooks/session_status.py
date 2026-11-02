"""SessionStart hook: tell Claude the state of the repo when a session begins.

Whatever this prints on stdout is added to Claude's context. It never fails:
if git is not available it prints nothing and exits 0.
"""

import subprocess
import sys

BASE = "origin/practice"


def git(*args):
    try:
        done = subprocess.run(["git", *args], capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return done.stdout.strip() if done.returncode == 0 else None


def build_status(branch, ahead_behind, dirty_count):
    lines = [f"Repo status: branch {branch}."]
    if ahead_behind:
        ahead, behind = ahead_behind
        lines.append(f"It is {ahead} commit(s) ahead and {behind} behind {BASE} (last fetch).")
    lines.append(f"{dirty_count} uncommitted file(s).")
    if branch in ("main", "practice"):
        lines.append(f"WARNING: on {branch}. Create a fix/, feat/ or docs/ branch before committing.")
    lines.append("Rules: no commit or push unless asked, no AI attribution lines, plain ASCII, stdlib only.")
    return "\n".join(lines)


def main():
    branch = git("rev-parse", "--abbrev-ref", "HEAD")
    if not branch:
        return 0
    counts = git("rev-list", "--left-right", "--count", f"HEAD...{BASE}")
    ahead_behind = tuple(int(n) for n in counts.split()) if counts else None
    status = git("status", "--porcelain")
    dirty = len(status.splitlines()) if status else 0
    print(build_status(branch, ahead_behind, dirty))
    return 0


if __name__ == "__main__":
    sys.exit(main())
