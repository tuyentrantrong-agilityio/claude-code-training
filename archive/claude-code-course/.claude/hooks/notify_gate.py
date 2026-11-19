"""Stop hook: tell the user when a kickoff gate is waiting for them.

Kickoff stages take a while and the user may step away. When Claude finishes a turn
and the active kickoff waits at a gate, show a desktop notification. Silent
otherwise, and never fails.
"""

import platform
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _kickoff import current_folder, project_dir, read_payload, waiting_gate  # noqa: E402

TITLE = "Auction kickoff"
BALLOON = (
    "Add-Type -AssemblyName System.Windows.Forms; "
    "$n = New-Object System.Windows.Forms.NotifyIcon; "
    "$n.Icon = [System.Drawing.SystemIcons]::Information; $n.Visible = $true; "
    "$n.ShowBalloonTip(8000, '{title}', '{message}', 'Info'); Start-Sleep -Seconds 8; $n.Dispose()"
)


def notify(message):
    try:
        if platform.system() == "Windows" and shutil.which("powershell"):
            script = BALLOON.format(title=TITLE, message=message.replace("'", ""))
            # Detached so the hook returns at once while the balloon stays up.
            subprocess.Popen(["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", script],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif shutil.which("notify-send"):
            subprocess.run(["notify-send", TITLE, message], capture_output=True, timeout=10)
        else:
            print("\a", end="", file=sys.stderr)
    except (OSError, subprocess.SubprocessError):
        pass


def main():
    gate = waiting_gate(current_folder(project_dir(read_payload())))
    if gate:
        notify(f"Gate {gate} is waiting for you. Review, then type: approve gate {gate}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
