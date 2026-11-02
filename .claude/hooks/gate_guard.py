"""PreToolUse hook: no GitLab issues for a kickoff until the user has approved Gate 3.

Creating issues is the step of a kickoff that others see and that cannot be quietly
undone, so it waits for `intent/<folder>/approvals/gate-3.md`, which only the user's
`approve gate 3` message creates (record_approval.py).

Guarded calls:
- The browser MCP opening a new-issue page (`/-/issues/new` or `/-/work_items/new`).
- Any MCP tool whose name creates an issue (for example `create_issue`).
- Shell: `glab issue create`, or a POST to a GitLab `/issues` API endpoint.
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _kickoff import current_folder, gate_approved, project_dir, read_payload  # noqa: E402

NEW_ISSUE_PAGE = re.compile(r"/-/(issues|work_items)/new\b")
MCP_ISSUE_WRITE = re.compile(r"^mcp__.*(create_issue|issue_write|create_work_item)", re.I)
GLAB_ISSUE = re.compile(r"\bglab\s+issue\s+create\b")
API_ISSUES = re.compile(r"/api/v4/projects/\S+/issues\b")
API_WRITE = re.compile(r"(-X|--request|-Method)\s*['\"]?(POST|PUT)|--data|\s-d\s|-Body\b", re.I)


def creates_issue(tool, tool_input):
    if tool in ("Bash", "PowerShell"):
        cmd = tool_input.get("command") or ""
        return bool(GLAB_ISSUE.search(cmd) or (API_ISSUES.search(cmd) and API_WRITE.search(cmd)))
    if tool.endswith("__navigate"):
        return bool(NEW_ISSUE_PAGE.search(str(tool_input.get("url") or "")))
    return bool(MCP_ISSUE_WRITE.match(tool))


def main():
    payload = read_payload()
    if not creates_issue(payload.get("tool_name") or "", payload.get("tool_input") or {}):
        return 0
    folder = current_folder(project_dir(payload))
    if folder is None or gate_approved(folder, 3):
        return 0  # no kickoff running: ordinary issue work is not this hook's business
    print(
        "Blocked by kickoff policy: GitLab issues are created only after Gate 3. "
        f"Ask the user to review {folder.name} and type `approve gate 3`.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
