"""Shared helpers for the kickoff hooks: project root, active kickoff folder, its state.

A missing or malformed kickoff never raises: it simply means there is nothing to guard.
"""

import json
import os
import re
import sys
from pathlib import Path

STAGES = ("brief", "intake", "answers", "pack", "dev-round", "promote", "reveal", "done")


def read_payload():
    try:
        data = json.load(sys.stdin)
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def project_dir(payload):
    root = os.environ.get("CLAUDE_PROJECT_DIR") or payload.get("cwd") or os.getcwd()
    return Path(root).resolve()


def current_folder(root):
    """The active intent folder named in intent/CURRENT, or None."""
    try:
        name = (root / "intent" / "CURRENT").read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if not name:
        return None
    folder = (root / name).resolve()
    return folder if folder.is_dir() else None


def read_state(folder):
    """`next`, `gate` and `dev_rounds` from <folder>/state.md, with defaults."""
    state = {"next": "brief", "gate": "none", "dev_rounds": ""}
    if folder is None:
        return state
    try:
        text = (folder / "state.md").read_text(encoding="utf-8")
    except OSError:
        return state
    for key in state:
        match = re.search(rf"^{key}:[ \t]*(.*?)[ \t]*$", text, re.M)
        if match:
            state[key] = match.group(1)
    return state


def gate_approved(folder, gate):
    return folder is not None and (folder / "approvals" / f"gate-{gate}.md").is_file()


def waiting_gate(folder):
    """The gate number the kickoff is stopped at, or None."""
    gate = read_state(folder)["gate"]
    if gate.isdigit() and not gate_approved(folder, gate):
        return gate
    return None


def relative(root, raw, cwd=None):
    """A tool path argument as a POSIX path relative to the project ('' if outside it)."""
    if not raw:
        return ""
    path = Path(raw)
    if not path.is_absolute():
        path = Path(cwd or root) / path
    try:
        return path.resolve().relative_to(root).as_posix()
    except ValueError:
        return ""


def emit(event, **fields):
    """Print a hookSpecificOutput JSON object for the given event."""
    print(json.dumps({"hookSpecificOutput": {"hookEventName": event, **fields}}))
