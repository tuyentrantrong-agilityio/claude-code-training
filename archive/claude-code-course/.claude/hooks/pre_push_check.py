"""PreToolUse hook (Bash, PowerShell): run the branch checklist before a branch push.

Retro of PR #12: check_branch.py printed FAIL (a non-ASCII arrow in a test), but its
output went through `| grep`, the push went on and CI went red. A rule in memory did
not stop it; this hook does. Before `git push` of a branch it runs
`.claude/skills/review-checklist/check_branch.py` against origin/practice and denies
the push, with the failing lines, if any check fails.

Not checked: pushing a tag (`git push origin v0.2.0`, `--tags`), and pushes while on
main or practice (block_forbidden.py already refuses those). The match is on the command
text, so a command that only mentions `git push` (in an echo, say) is also held while
the checklist fails; that errs on the safe side.
"""

import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _kickoff import emit, project_dir, read_payload  # noqa: E402

# git, then options that may take a value (`-C /repo`, `-c k=v`), then push and its arguments.
GIT_PUSH = re.compile(r"\bgit\s+(?:-\S+(?:\s+[^-\s]\S*)?\s+)*push\b(?P<args>[^;&|\n]*)")
TAG = re.compile(r"^v\d+(\.\d+)*$")
PROTECTED = {"main", "practice"}


def pushes_a_branch(command):
    """True when the command has a `git push` that is not only a tag push."""
    for match in GIT_PUSH.finditer(command):
        args = match.group("args").split()
        if "--tags" in args:
            continue
        refs = [a for a in args if not a.startswith("-")][1:]
        if refs and all(TAG.match(r.split(":")[-1]) for r in refs):
            continue
        return True
    return False


def current_branch(root):
    done = subprocess.run(["git", "symbolic-ref", "--short", "HEAD"], cwd=root,
                          capture_output=True, text=True, timeout=10)
    return done.stdout.strip()


def run_checklist(root):
    script = root / ".claude" / "skills" / "review-checklist" / "check_branch.py"
    done = subprocess.run([sys.executable, str(script)], cwd=root,
                          capture_output=True, text=True, timeout=60)
    return done.returncode, done.stdout + done.stderr


def decide(command, root, branch=None, checklist=run_checklist):
    """Return a deny reason, or None to let the command run."""
    if not pushes_a_branch(command):
        return None
    if (branch if branch is not None else current_branch(root)) in PROTECTED:
        return None
    code, output = checklist(root)
    if code == 0:
        return None
    failing = "\n".join(line for line in output.splitlines() if line.startswith(("[FAIL]", "       ")))
    return ("check_branch.py fails, so this branch is not pushed. Fix these first "
            "(amend only commits that are not pushed yet):\n" + failing)


def main():
    payload = read_payload()
    command = (payload.get("tool_input") or {}).get("command") or ""
    reason = decide(command, project_dir(payload))
    if reason:
        emit("PreToolUse", permissionDecision="deny", permissionDecisionReason=reason)
    return 0


if __name__ == "__main__":
    sys.exit(main())
