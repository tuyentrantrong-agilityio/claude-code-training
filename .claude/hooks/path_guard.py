"""PreToolUse hook: keep each kickoff role inside the files it is allowed to see.

Roles talk only through files. A Dev that can read the brief, or a BA that can read
the client's private notes, would make the kickoff scores meaningless. An agent's
`tools` list limits which tools it has; this hook limits which paths they touch.

The hook input has `agent_type` (the subagent's name) when a subagent makes the call.
- lead, ba, qa, dev: read and write only the paths in READ and WRITE. No Bash.
  Glob and Grep need a `path` inside the allowed area.
- Everyone else (the main conversation, other subagents): no reading of
  `.kickoff-private/` before the reveal stage, no writing there at all.
- Nobody writes `intent/*/approvals/`: only the user's `approve gate N` creates them.

A denial is a JSON permission decision with the reason, which Claude sees.
"""

import fnmatch
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _kickoff import current_folder, emit, project_dir, read_payload, read_state, relative  # noqa: E402

COMMON = ["docs/*", "CONTEXT.md", "intent/CURRENT"]
READ = {
    "lead": COMMON + [".kickoff-private/*", "intent/*/brief.md", "intent/*/intake.md"],
    "ba": COMMON + [".claude/rules/*", "intent/*/brief.md", "intent/*/intake.md", "intent/*/spec.md",
                    "intent/*/tickets/*", "intent/*/test-matrix.md"],
    "qa": COMMON + [".claude/rules/*", "intent/*/spec.md", "intent/*/tickets/*", "intent/*/test-matrix.md"],
    "dev": COMMON + [".claude/rules/*", "intent/*/spec.md", "intent/*/tickets/*",
                     "day-02/auction/*", "day-02/tests/*", "day-11/webapp/*", "day-11/tests/*"],
}
WRITE = {
    "lead": [".kickoff-private/client-truth.md", "intent/*/brief.md", "intent/*/intake.md"],
    "ba": ["intent/*/intake.md", "intent/*/spec.md", "intent/*/tickets/*.md", "CONTEXT.md"],
    "qa": ["intent/*/test-matrix.md", "intent/*/tickets/*.md"],
    "dev": [],
}
WRITE_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}
SEARCH_TOOLS = {"Glob", "Grep"}
SHELL_TOOLS = {"Bash", "PowerShell"}
PRIVATE = ".kickoff-private"
APPROVALS = re.compile(r"(^|/)intent/[^/]+/approvals(/|$)")
# A shell command touches approval files only if it names their path, not just the word.
APPROVALS_IN_SHELL = re.compile(r"approvals[/\\]|intent[/\\]\S*approvals\b")
REVEALED = {"reveal", "done"}
SHELL_WRITES = re.compile(
    r">|\b(rm|mv|cp|touch|tee|sed|mkdir|python3?|echo|printf|ln|truncate|"
    r"set-content|add-content|out-file|new-item|remove-item|move-item|copy-item)\b",
    re.I,
)


def matches(path, patterns):
    return any(fnmatch.fnmatch(path, p) for p in patterns)


def target_path(tool, tool_input):
    if tool in SEARCH_TOOLS:
        return tool_input.get("path") or ""
    return tool_input.get("file_path") or tool_input.get("notebook_path") or ""


def check_role(role, tool, rel, raw):
    if tool in SHELL_TOOLS:
        return f"the {role} agent has no shell; work through files"
    if tool in WRITE_TOOLS:
        if not rel or not matches(rel, WRITE[role]):
            allowed = ", ".join(WRITE[role]) or "nothing (read-only role)"
            return f"the {role} agent may write only: {allowed}"
        return None
    if tool in SEARCH_TOOLS and not raw:
        return f"the {role} agent must pass a `path` to {tool}, inside: {', '.join(READ[role])}"
    # A directory is fine when something allowed lives under it, e.g. Glob in intent/x/tickets.
    if not rel or not (matches(rel, READ[role]) or matches(rel + "/x", READ[role])):
        return f"the {role} agent may read only: {', '.join(READ[role])}"
    return None


def check_everyone(tool, rel, command):
    if tool in WRITE_TOOLS and APPROVALS.search(rel):
        return "approval files are written only when the user types `approve gate N`"
    if tool in SHELL_TOOLS and APPROVALS_IN_SHELL.search(command) and SHELL_WRITES.search(command):
        return "approval files are written only when the user types `approve gate N`"
    return None


def check_others(tool, rel, command, stage):
    private = rel == PRIVATE or rel.startswith(PRIVATE + "/")
    if tool in WRITE_TOOLS and private:
        return "only the lead agent writes the client's private notes"
    if stage not in REVEALED:
        if private or (tool in SHELL_TOOLS and PRIVATE in command):
            return "the client's private notes stay hidden until the reveal stage"
    return None


def decide(payload):
    tool = payload.get("tool_name") or ""
    tool_input = payload.get("tool_input") or {}
    root = project_dir(payload)
    raw = target_path(tool, tool_input)
    rel = relative(root, raw, payload.get("cwd")) if raw else ""
    command = (tool_input.get("command") or "") if tool in SHELL_TOOLS else ""
    reason = check_everyone(tool, rel, command)
    if reason:
        return reason
    role = payload.get("agent_type") or ""
    if role in READ:
        return check_role(role, tool, rel, raw)
    return check_others(tool, rel, command, read_state(current_folder(root))["next"])


def main():
    reason = decide(read_payload())
    if reason:
        emit("PreToolUse", permissionDecision="deny", permissionDecisionReason=f"Kickoff policy: {reason}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
