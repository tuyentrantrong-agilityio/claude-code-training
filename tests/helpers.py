"""A throwaway project with an active kickoff, and a way to run a hook against it."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
HOOKS = REPO / ".claude" / "hooks"
FOLDER = "intent/2026-11-03-auction-end-time"

GOOD_TICKET = """\
# T-01 Show when an auction ends

Status: draft
Spec: [Behaviour](../spec.md#behaviour)

## Story

As a bidder
I want to see when each auction ends
So that I can bid before it closes

## Scenarios

### S1 End time shown in my bids

Given auction 7 ends at 2026-12-01 18:00 UTC and user 42 bid 100 on it
When user 42 lists their bids
Then the item for auction 7 has ends_at "2026-12-01T18:00:00Z"

### S2 Bid after the end is rejected

Given auction 7 ended at 2026-12-01 18:00 UTC
When user 42 bids 120 at 18:01
Then the API returns 409 "auction has ended" and nothing is stored

## Out of scope

- Extending the end time when a late bid arrives.

## Questions

- None yet.
"""

MATRIX = """\
| ID | Ticket | Scenario | Type | Preconditions | Input | Expected | Planned test |
|---|---|---|---|---|---|---|---|
| M-001 | T-01 | S1 | happy | Auction 7 ends 18:00 | list bids | ends_at shown | `day-02/tests/test_end.py::test_a` |
| M-002 | T-01 | S2 | negative | Auction 7 ended | bid 120 at 18:01 | 409 | `day-02/tests/test_end.py::test_b` |
"""


class ProjectTestCase(unittest.TestCase):
    """Each test gets a fresh project root waiting at Gate 1."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name).resolve()
        self.folder = self.root / FOLDER
        (self.folder / "tickets").mkdir(parents=True)
        (self.root / "intent" / "CURRENT").write_text(FOLDER + "\n", encoding="utf-8")
        self.set_state("answers", "1")
        (self.root / ".kickoff-private").mkdir()
        (self.root / ".kickoff-private" / "client-truth.md").write_text("# Client truth\n", encoding="utf-8")
        shutil.copytree(REPO / "scripts", self.root / "scripts", ignore=shutil.ignore_patterns("__pycache__"))

    def tearDown(self):
        self._tmp.cleanup()

    def set_state(self, next_stage, gate="none"):
        (self.folder / "state.md").write_text(
            f"# Kickoff state\n\nnext: {next_stage}\ngate: {gate}\ndev_rounds:\n\n## Log\n", encoding="utf-8"
        )

    def write_ticket(self, text=GOOD_TICKET, name="T-01-show-auction-end.md"):
        (self.folder / "tickets" / name).write_text(text, encoding="utf-8")

    def run_hook(self, name, payload, *args):
        env = {**os.environ, "CLAUDE_PROJECT_DIR": str(self.root)}
        return subprocess.run(
            [sys.executable, str(HOOKS / name), *args],
            input=json.dumps({"cwd": str(self.root), **payload}),
            capture_output=True, text=True, env=env, timeout=60,
        )

    def hook_output(self, result):
        return json.loads(result.stdout)["hookSpecificOutput"] if result.stdout.strip() else {}

    def denied(self, result):
        return self.hook_output(result).get("permissionDecision") == "deny"
