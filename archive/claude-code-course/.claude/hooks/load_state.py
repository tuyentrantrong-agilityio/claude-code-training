"""SessionStart hook and status line: where the active kickoff stands.

A kickoff spans several sessions (the user steps away at gates), so a new session
gets the folder, the next stage and any waiting gate as context.
With --statusline it prints one short line for the status bar instead.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _kickoff import current_folder, emit, project_dir, read_payload, read_state, waiting_gate  # noqa: E402


def summary(root):
    """(context for Claude, status line text)."""
    folder = current_folder(root)
    if folder is None:
        return "No kickoff is running in this repo. `/kickoff` starts one.", "kickoff: none"
    state = read_state(folder)
    gate = waiting_gate(folder)
    name = folder.name
    if gate:
        return (
            f"Active kickoff: {name}. It is stopped at Gate {gate}, waiting for the user to review "
            f"and type `approve gate {gate}`. Next stage after approval: {state['next']}.",
            f"kickoff {name} | Gate {gate} waiting",
        )
    if state["next"] == "done":
        return f"Kickoff {name} is finished.", f"kickoff {name} | done"
    return (
        f"Active kickoff: {name}. Next stage: {state['next']} (run `/kickoff`).",
        f"kickoff {name} | next: {state['next']}",
    )


def main(argv):
    context, line = summary(project_dir(read_payload()))
    if "--statusline" in argv:
        print(line)
    else:
        emit("SessionStart", additionalContext=context)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
