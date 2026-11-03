"""Run the real hook scripts on safe sample inputs and print what each one does.

Nothing here touches git or the network: the hooks only read a JSON payload on stdin.
Usage: python scripts/hook_proof.py > docs/hook-proof.md
"""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOOKS = ROOT / ".claude" / "hooks"

CASES = [
    ("block_forbidden.py", "PreToolUse Bash: force push",
     {"tool_name": "Bash", "tool_input": {"command": "git push --force origin fix/x"}}),
    ("block_forbidden.py", "PreToolUse Bash: push to practice",
     {"tool_name": "Bash", "tool_input": {"command": "git push origin practice"}}),
    ("block_forbidden.py", "PreToolUse Bash: harmless command",
     {"tool_name": "Bash", "tool_input": {"command": "git status"}}),
    ("block_secrets.py", "PreToolUse Write: .env file",
     {"tool_name": "Write", "tool_input": {"file_path": str(ROOT / ".env"), "content": "X=1"}}),
    ("gate_guard.py", "PreToolUse Bash: new issue before Gate 3",
     {"tool_name": "Bash", "tool_input": {"command": "gh issue create --title t --body b"}}),
    ("path_guard.py", "PreToolUse Write: approval file",
     {"tool_name": "Write", "tool_input": {
         "file_path": str(ROOT / "intent" / "x" / "approvals" / "gate-1.md"), "content": "ok"}}),
    ("record_approval.py", "UserPromptSubmit: 'ok' is not an approval",
     {"prompt": "ok", "cwd": str(ROOT)}),
]


def run(script, payload):
    done = subprocess.run([sys.executable, str(HOOKS / script)], input=json.dumps(payload),
                          capture_output=True, text=True, cwd=ROOT)
    text = (done.stdout + done.stderr).strip() or "(no output)"
    return done.returncode, text


def main():
    print("# Hook proof\n")
    print("Produced by `python scripts/hook_proof.py`: each real hook script is run on a sample")
    print("payload. Exit code 2 or a deny decision means the hook blocked the action.\n")
    for script, label, payload in CASES:
        code, text = run(script, payload)
        print(f"## {script}: {label}\n")
        print(f"- Exit code: {code}")
        print("- Output:\n")
        print("```")
        print(text[:600])
        print("```\n")


if __name__ == "__main__":
    main()
