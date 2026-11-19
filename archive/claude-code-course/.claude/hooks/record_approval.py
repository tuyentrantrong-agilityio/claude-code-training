"""UserPromptSubmit hook: turn the user's `approve gate N` message into an approval file.

A gate is a human decision, so the approval must come from words the user typed,
not from Claude reading "ok" as a yes. When the prompt starts with `approve gate N`
and the active kickoff waits at gate N, this writes
`intent/<folder>/approvals/gate-N.md` with the time and the user's exact words.
path_guard.py stops Claude from writing those files itself.
"""

import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _kickoff import current_folder, emit, gate_approved, project_dir, read_payload, read_state  # noqa: E402

APPROVE = re.compile(r"^\s*/?approve\s+gate\s*-?\s*([123])\b", re.I)
# Context the IDE puts in front of what the user typed, e.g. <ide_opened_file>...</ide_opened_file>.
# Greedy on purpose: selected text may contain a closing tag, so a block ends at its LAST
# closing tag; text after an early one, such as a fake "approve gate N", stays hidden.
IDE_CONTEXT = re.compile(r"^\s*<(ide_[a-z_]+)>.*</\1>", re.S)


def typed_text(prompt):
    """The prompt without the IDE context blocks in front of it."""
    while True:
        match = IDE_CONTEXT.match(prompt)
        if not match:
            return prompt
        prompt = prompt[match.end():]


def handle(payload):
    """Return the context note for Claude, or None when the prompt is not an approval."""
    prompt = typed_text(payload.get("prompt") or "")
    match = APPROVE.match(prompt)
    if not match:
        return None
    gate = match.group(1)
    folder = current_folder(project_dir(payload))
    if folder is None:
        return (f"Kickoff hook: the user typed 'approve gate {gate}', but no kickoff is running "
                "(intent/CURRENT is missing). Nothing was recorded.")
    if gate_approved(folder, gate):
        return f"Kickoff hook: gate {gate} of {folder.name} was already approved. Nothing new recorded."
    waiting = read_state(folder)["gate"]
    if waiting != gate:
        return (f"Kickoff hook: the user typed 'approve gate {gate}', but {folder.name} is waiting at "
                f"gate '{waiting}'. Nothing was recorded; tell the user which gate is waiting.")
    approvals = folder / "approvals"
    approvals.mkdir(exist_ok=True)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    (approvals / f"gate-{gate}.md").write_text(
        f"# Gate {gate} approved\n\n"
        f"- When: {now}\n"
        f"- Session: {payload.get('session_id', 'unknown')}\n"
        f"- Typed by the user:\n\n> {prompt.strip()}\n",
        encoding="utf-8",
    )
    return (f"Kickoff hook: the user approved gate {gate} of {folder.name}; recorded in "
            f"{folder.name}/approvals/gate-{gate}.md. Set `gate: none` in state.md and run the next "
            "kickoff stage now. Any text after 'approve gate N' is the user's note for that stage.")


def main():
    note = handle(read_payload())
    if note:
        emit("UserPromptSubmit", additionalContext=note)
    return 0


if __name__ == "__main__":
    sys.exit(main())
