"""SubagentStop hook (ba, qa): do not let the BA or QA finish with a malformed ticket pack.

Runs scripts/lint_tickets.py on the active kickoff folder. On problems the subagent
is kept going (exit 2) with the problems as its next instruction. It does this once
per stop: if the subagent already continues because of a stop hook
(`stop_hook_active`), it may stop, and /kickoff's own lint step reports the rest.
"""

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _kickoff import current_folder, project_dir, read_payload  # noqa: E402


def main():
    payload = read_payload()
    if payload.get("stop_hook_active"):
        return 0
    root = project_dir(payload)
    folder = current_folder(root)
    if folder is None or not (folder / "tickets").is_dir():
        return 0  # nothing to lint before the pack stage
    result = subprocess.run(
        [sys.executable, str(root / "scripts" / "lint_tickets.py"), str(folder)],
        capture_output=True, text=True, timeout=60,
    )
    if result.returncode != 1:
        return 0
    # Each role answers only for the files it may write.
    prefix = "test-matrix.md" if payload.get("agent_type") == "qa" else "tickets/"
    problems = "\n".join(line for line in result.stdout.splitlines() if line.startswith(prefix))
    if not problems.strip():
        return 0
    print(
        "The ticket pack does not pass scripts/lint_tickets.py yet. Fix these "
        "(formats in .claude/rules/), then finish:\n" + problems,
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
