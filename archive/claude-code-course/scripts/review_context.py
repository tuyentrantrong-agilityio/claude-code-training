"""Prepare what the reviewer agent reads, so it needs no shell.

Usage: python scripts/review_context.py [--base origin/practice] [--head HEAD] [--issue N]

Writes `.review/<head name>/`:
- tree/: a git worktree of <head>, so checks and the reviewer see the code under
  review, not whatever is checked out here
- diff.patch: `git diff <base>...<head>`
- context.md: commits, changed files, the ticket whose `Issue: #N` line matches
  (with its spec and test matrix rows), and the output of the head's own checks
  (branch checklist, matrix against tests, all test suites), run inside tree/.

Prints the folder. Standard library only; needs git.
"""

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from lint_tickets import matrix_rows  # noqa: E402


def git(*args, cwd=ROOT):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True).stdout


def run(tree, script, *args):
    """Run a script from the head's own tree, or say that the head does not have it."""
    if not (tree / script).is_file():
        return f"{script} does not exist at this head"
    done = subprocess.run([sys.executable, script, *args], cwd=tree, capture_output=True, text=True)
    return (done.stdout + done.stderr).strip()


def checkout(head, out):
    tree = out / "tree"
    if tree.exists():
        git("worktree", "remove", "--force", str(tree))
    git("worktree", "prune")
    git("worktree", "add", "--detach", str(tree), head)
    return tree


def find_ticket(tree, issue):
    for path in sorted(tree.glob("intent/*/tickets/T-*.md")):
        if re.search(rf"^Issue: #{issue}\s*$", path.read_text(encoding="utf-8"), re.M):
            return path
    return None


def ticket_section(ticket):
    if ticket is None:
        return ["No ticket found for this change. Review against CLAUDE.md and the rules only."]
    folder = ticket.parent.parent
    number = ticket.name[:4]
    rel = lambda p: p.relative_to(ROOT).as_posix()  # noqa: E731
    rows = matrix_rows(folder / "test-matrix.md") if (folder / "test-matrix.md").exists() else []
    lines = [
        f"- Ticket: `{rel(ticket)}`",
        f"- Spec: `{rel(folder / 'spec.md')}`",
        f"- Evidence: `{rel(folder / 'evidence' / number)}/`",
        "",
        f"Test matrix rows for {number}:",
        "",
        "| ID | Scenario | Type | Expected | Planned test |",
        "|---|---|---|---|---|",
    ]
    lines += [f"| {r[0]} | {r[2]} | {r[3]} | {r[6]} | {r[7]} |" for r in rows if r[1] == number]
    # This repo's checker, run on the head's folder (its root is the head's tree).
    done = subprocess.run([sys.executable, str(ROOT / "scripts" / "check_matrix.py"), str(folder)],
                          capture_output=True, text=True)
    return lines + ["", "`scripts/check_matrix.py`:", "", "```", (done.stdout + done.stderr).strip(), "```"]


def main(argv):
    opts = {"--base": "origin/practice", "--head": "HEAD", "--issue": None}
    for i in range(0, len(argv), 2):
        if argv[i] not in opts or i + 1 >= len(argv):
            print("usage: python scripts/review_context.py [--base REF] [--head REF] [--issue N]", file=sys.stderr)
            return 2
        opts[argv[i]] = argv[i + 1]
    base, head = str(opts["--base"]), str(opts["--head"])
    name = git("rev-parse", "--abbrev-ref", head).strip() if head == "HEAD" else head
    out = ROOT / ".review" / re.sub(r"[^\w.-]+", "-", name)
    out.mkdir(parents=True, exist_ok=True)
    tree = checkout(head, out)
    (out / "diff.patch").write_text(git("diff", f"{base}...{head}"), encoding="utf-8")
    commits = git("log", "--format=- %h %s", f"{base}..{head}").strip()
    files = git("diff", "--stat", f"{base}...{head}").strip()
    ticket = find_ticket(tree, opts["--issue"]) if opts["--issue"] else None
    tree_rel = tree.relative_to(ROOT).as_posix()
    context = [
        f"# Review context: {name}",
        "",
        f"Base `{base}`, head `{head}`. The diff is in `diff.patch` next to this file.",
        f"The code at the head is checked out in `{tree_rel}/`: read every file there,",
        "not at the repo root (the root may be on another branch).",
        "",
        "## Commits",
        "",
        commits or "- none",
        "",
        "## Changed files",
        "",
        "```",
        files,
        "```",
        "",
        "## Ticket",
        "",
        *ticket_section(ticket),
        "",
        "## Repo checks (run inside the head's tree)",
        "",
        "`check_branch.py`:",
        "",
        "```",
        run(tree, ".claude/skills/review-checklist/check_branch.py", base),
        "```",
        "",
        "`run_tests.py`:",
        "",
        "```",
        run(tree, ".claude/skills/run-tests/run_tests.py"),
        "```",
    ]
    (out / "context.md").write_text("\n".join(context) + "\n", encoding="utf-8")
    print(out.relative_to(ROOT).as_posix())
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
