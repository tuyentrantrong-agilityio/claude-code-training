"""Run the scripts behind the skills and print what each one reports.

Each skill in .claude/skills is a procedure; the checks below are the commands those
procedures run. Read-only: nothing is written to git or the network.
Usage: python scripts/skill_proof.py > docs/skill-proof.md
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable

RUNS = [
    ("run-tests", "all suites, one summary",
     [PY, ".claude/skills/run-tests/run_tests.py"], 6),
    ("review-checklist", "branch against the CLAUDE.md rules",
     [PY, ".claude/skills/review-checklist/check_branch.py", "origin/practice"], 12),
    ("write-ticket / test-matrix", "ticket lint on the cancel bid kickoff",
     [PY, "scripts/lint_tickets.py", "intent/2026-11-02-cancel-bid"], 12),
    ("test-matrix", "every matrix row has its real test",
     [PY, "scripts/check_matrix.py", "intent/2026-11-02-cancel-bid"], 12),
    ("kickoff", "scorecard of the finished kickoff",
     [PY, "scripts/score_kickoff.py", "intent/2026-11-02-cancel-bid"], 12),
    ("release", "notes generated for the range v0.2.0..v0.3.0",
     [PY, "scripts/release_notes.py", "v0.3.0", "--since", "v0.2.0", "--to", "v0.3.0"], 12),
]

USED = [
    ("kickoff", "intent/2026-11-02-cancel-bid/ (state, gates, scorecard, recall)"),
    ("write-ticket, test-matrix", "intent/2026-11-02-cancel-bid/tickets/ and test-matrix.md"),
    ("review-pr", "PRs #28 to #32: findings fixed in follow-up commits, see each PR"),
    ("evidence", "intent/2026-11-02-cancel-bid/evidence/T-01 to T-04"),
    ("release", "docs/releases/v0.3.0.md, PRs #34 and #35, tag v0.3.0"),
    ("run-tests, review-checklist", "run before every push (the pre_push_check hook runs check_branch)"),
    ("fix-ticket", "not used yet in this repo: no record exists, so none is claimed"),
]


def main():
    print("# Skill proof\n")
    print("Produced by `python scripts/skill_proof.py`: the command behind each skill is run")
    print("and its real output is shown, cut to the last 12 lines.\n")
    for name, what, cmd, _ in RUNS:
        out = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=300)
        lines = (out.stdout + out.stderr).strip().splitlines()
        print(f"## {name}: {what}\n")
        print(f"- Command: `{' '.join('python' if c == PY else c for c in cmd)}`")
        print(f"- Exit code: {out.returncode}")
        print("- Output (end):\n\n```")
        print("\n".join(l.encode("ascii", "replace").decode() for l in lines[-12:]))
        print("```\n")
    print("## Where the skills were used\n")
    print("| Skill | Trace in the repo |\n|---|---|")
    for skill, trace in USED:
        print(f"| {skill} | {trace} |")


if __name__ == "__main__":
    main()
