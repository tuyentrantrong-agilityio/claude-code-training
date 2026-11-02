"""Write release notes from the merges since the last tag.

Usage: python scripts/release_notes.py VERSION [--since TAG] [--to REF] [--out FILE]

- Changes: every merged pull request (GitHub `Merge pull request #N`) or merge request
  (GitLab `Merge branch ... See merge request ...!N`) between --since (default: the
  newest tag) and --to (default: origin/practice), grouped by the type of its title.
- Kickoffs: every `intent/<folder>/` touched in that range, with its tickets, their
  issues, whether evidence exists, and the scorecard's readiness and recall lines.

Prints the notes, or writes them to --out. Standard library only; needs git.
"""

import re
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TYPES = [("feat", "Features"), ("fix", "Fixes"), ("test", "Tests"), ("docs", "Docs"),
         ("refactor", "Refactoring"), ("chore", "Chores")]
GITHUB = re.compile(r"^Merge pull request #(\d+) from \S+$")
GITLAB_REF = re.compile(r"See merge request \S+!(\d+)")
TITLE = re.compile(r"^(\w+): (.+)$")
SCORE_LINES = ("Ready at round 1", "Contradiction flagged", "BA recall", "Hidden requirements recall", "Missed")


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout


def parse_merges(log):
    """Merges from `git log --merges --format=%s%x1f%b%x1e`, oldest first.

    Returns dicts with ref ("#13" or "GitLab !27"), type and title.
    """
    merges = []
    for record in log.split("\x1e"):
        if not record.strip():
            continue
        subject, _, body = record.strip().partition("\x1f")
        lines = [line.strip() for line in body.splitlines() if line.strip()]
        github = GITHUB.match(subject)
        gitlab = GITLAB_REF.search(body)
        if github:
            ref = f"#{github.group(1)}"
        elif gitlab:
            ref = f"GitLab !{gitlab.group(1)}"
        else:
            continue  # a local merge, not a reviewed change
        title = next((line for line in lines if not GITLAB_REF.search(line)), subject)
        match = TITLE.match(title)
        kind, text = (match.group(1), match.group(2)) if match else ("chore", title)
        merges.append({"ref": ref, "type": kind if kind in dict(TYPES) else "chore", "title": text})
    return list(reversed(merges))


def changes_section(merges):
    out = []
    for kind, heading in TYPES:
        items = [m for m in merges if m["type"] == kind]
        if items:
            out += [f"### {heading}", ""] + [f"- {m['title']} ({m['ref']})" for m in items] + [""]
    return out or ["No merged changes in this range.", ""]


def kickoff_section(folder):
    out = [f"### {folder.name}", ""]
    for ticket in sorted((folder / "tickets").glob("T-*.md")):
        text = ticket.read_text(encoding="utf-8")
        title = text.splitlines()[0].lstrip("# ").strip()
        issue = re.search(r"^Issue: (#\d+)", text, re.M)
        built = (folder / "evidence" / ticket.name[:4]).is_dir()
        out.append(f"- {title}: issue {issue.group(1) if issue else 'none'}, "
                   + ("built, evidence in `evidence/" + ticket.name[:4] + "/`" if built else "not built"))
    score = folder / "scorecard.md"
    if score.exists():
        lines = [line for line in score.read_text(encoding="utf-8").splitlines()
                 if line.startswith("- ") and line[2:].startswith(SCORE_LINES)]
        out += ["", "Scorecard:", ""] + lines
    return out + [""]


def render(version, since, to, merges, kickoffs, today=None):
    out = [
        f"# Release {version}",
        "",
        f"Date: {today or date.today().isoformat()}. Range: `{since}..{to}`, "
        f"{len(merges)} merged change{'s' if len(merges) != 1 else ''}.",
        "",
        "## Changes",
        "",
        *changes_section(merges),
        "## Kickoffs",
        "",
    ]
    if kickoffs:
        for folder in kickoffs:
            out += kickoff_section(folder)
    else:
        out += ["No kickoff in this range.", ""]
    return "\n".join(out).rstrip() + "\n"


def main(argv):
    if not argv or argv[0].startswith("--"):
        print("usage: python scripts/release_notes.py VERSION [--since TAG] [--to REF] [--out FILE]", file=sys.stderr)
        return 2
    version, opts = argv[0], {"--since": None, "--to": "origin/practice", "--out": None}
    rest = argv[1:]
    for i in range(0, len(rest), 2):
        if rest[i] not in opts or i + 1 >= len(rest):
            print(f"unknown or incomplete option: {rest[i]}", file=sys.stderr)
            return 2
        opts[rest[i]] = rest[i + 1]
    # Tags sit on main, which practice never merges back, so take the newest tag, not `describe`.
    tags = git("tag", "--sort=-creatordate").split()
    since = opts["--since"] or (tags[0] if tags else None)
    if not since:
        print("no tag yet: pass --since <ref>", file=sys.stderr)
        return 2
    to = str(opts["--to"])
    log = git("log", "--merges", "--format=%s%x1f%b%x1e", f"{since}..{to}")
    touched = git("diff", "--name-only", f"{since}...{to}", "--", "intent/").split()
    names = sorted({p.split("/")[1] for p in touched if p.count("/") >= 2})
    kickoffs = [ROOT / "intent" / n for n in names if (ROOT / "intent" / n / "tickets").is_dir()]
    notes = render(version, since, to, parse_merges(log), kickoffs)
    if opts["--out"]:
        Path(opts["--out"]).write_text(notes, encoding="utf-8")
        print(f"wrote {opts['--out']}")
    else:
        print(notes, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
