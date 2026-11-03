"""Run the real hook scripts on safe sample inputs and print what each one does.

Nothing here touches git, the network or this repo's kickoffs: the hooks read a JSON
payload on stdin, and the gate cases run against a throwaway project in a temp folder
whose kickoff waits at Gate 3, so the output does not depend on the real kickoff state.
Usage: python scripts/hook_proof.py > docs/hook-proof.md
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOOKS = ROOT / ".claude" / "hooks"
ISSUE = "gh issue create --title t --body b"


def make_cases(project):
    approvals = str(project / "intent" / "demo" / "approvals" / "gate-3.md")
    bash = lambda command: {"tool_name": "Bash", "tool_input": {"command": command}}
    return [
        ("block_forbidden.py", "PreToolUse Bash: force push", bash("git push --force origin fix/x")),
        ("block_forbidden.py", "PreToolUse Bash: push to practice", bash("git push origin practice")),
        ("block_forbidden.py", "PreToolUse Bash: harmless command", bash("git status")),
        ("block_secrets.py", "PreToolUse Write: .env file",
         {"tool_name": "Write", "tool_input": {"file_path": str(project / ".env"), "content": "X=1"}}),
        ("gate_guard.py", "PreToolUse Bash: new issue while Gate 3 waits", bash(ISSUE)),
        ("path_guard.py", "PreToolUse Write: approval file",
         {"tool_name": "Write", "tool_input": {"file_path": approvals, "content": "ok"}}),
        ("record_approval.py", "UserPromptSubmit: 'ok' is not an approval", {"prompt": "ok", "cwd": str(project)}),
        ("record_approval.py", "UserPromptSubmit: 'approve gate 3' typed by the user",
         {"prompt": "approve gate 3", "cwd": str(project)}),
        ("gate_guard.py", "PreToolUse Bash: new issue after Gate 3 was approved", bash(ISSUE)),
    ]


def run(script, payload, project):
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(project)}
    done = subprocess.run([sys.executable, str(HOOKS / script)], input=json.dumps(payload),
                          capture_output=True, text=True, cwd=ROOT, env=env)
    text = (done.stdout + done.stderr).strip() or "(no output)"
    return done.returncode, text


def main():
    with tempfile.TemporaryDirectory() as tmp:
        project = Path(tmp).resolve()
        (project / "intent" / "demo").mkdir(parents=True)
        (project / "intent" / "CURRENT").write_text("intent/demo\n", encoding="utf-8")
        (project / "intent" / "demo" / "state.md").write_text("next: promote\ngate: 3\n", encoding="utf-8")
        print("# Hook proof\n")
        print("Produced by `python scripts/hook_proof.py`: each real hook script is run on a sample")
        print("payload. Exit code 2 or a deny decision means the hook blocked the action. The gate")
        print("cases use a throwaway kickoff that waits at Gate 3, so they run in this order.\n")
        for script, label, payload in make_cases(project):
            code, text = run(script, payload, project)
            print(f"## {script}: {label}\n")
            print(f"- Exit code: {code}")
            print("- Output:\n")
            print("```")
            print(text.replace(str(project), "<project>")[:600])
            print("```\n")


if __name__ == "__main__":
    main()
