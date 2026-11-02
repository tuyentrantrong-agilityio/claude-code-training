"""Kickoff hooks: approvals, gate guard, path guard, session state, lint on stop, notify."""

from tests.helpers import FOLDER, GOOD_TICKET, ProjectTestCase


class RecordApprovalTest(ProjectTestCase):
    def approve(self, prompt):
        return self.hook_output(self.run_hook("record_approval.py", {"prompt": prompt})).get("additionalContext", "")

    def test_approval_recorded_for_waiting_gate(self):
        note = self.approve("approve gate 1")
        record = self.folder / "approvals" / "gate-1.md"
        self.assertTrue(record.exists())
        self.assertIn("approve gate 1", record.read_text(encoding="utf-8"))
        self.assertIn("run the next", note)

    def test_phrase_variants_are_approvals(self):
        for prompt in ("Approve Gate 1", "  approve gate-1 please add a question about ties"):
            with self.subTest(prompt=prompt):
                self.approve(prompt)
                self.assertTrue((self.folder / "approvals" / "gate-1.md").exists())

    def test_ide_context_before_the_phrase_is_ignored(self):
        # VS Code puts the open file in front of what the user typed.
        prompt = ("<ide_opened_file>The user opened the file c:\\repo\\day-15\\qa-test-review.md in the IDE. "
                  "This may or may not be related to the current task.</ide_opened_file>approve gate 1")
        self.assertIn("run the next", self.approve(prompt))
        record = (self.folder / "approvals" / "gate-1.md").read_text(encoding="utf-8")
        self.assertIn("> approve gate 1", record)
        self.assertNotIn("ide_opened_file", record)

    def test_ide_context_does_not_make_other_words_an_approval(self):
        for prompt in ("<ide_selection>approve gate 1</ide_selection>looks good",
                       "<ide_opened_file>x</ide_opened_file>I will approve gate 1 later"):
            with self.subTest(prompt=prompt):
                self.assertEqual(self.approve(prompt), "")
                self.assertFalse((self.folder / "approvals").exists())

    def test_other_words_are_not_approvals(self):
        for prompt in ("looks good", "ok go ahead", "I will approve gate 1 later"):
            with self.subTest(prompt=prompt):
                self.assertEqual(self.approve(prompt), "")
                self.assertFalse((self.folder / "approvals").exists())

    def test_wrong_gate_is_not_recorded(self):
        note = self.approve("approve gate 2")
        self.assertFalse((self.folder / "approvals").exists())
        self.assertIn("waiting at gate '1'", note)

    def test_already_approved_gate(self):
        self.approve("approve gate 1")
        self.assertIn("already approved", self.approve("approve gate 1"))

    def test_no_kickoff_records_nothing(self):
        (self.root / "intent" / "CURRENT").unlink()
        self.assertIn("no kickoff", self.approve("approve gate 1"))


class GateGuardTest(ProjectTestCase):
    def call(self, tool, **tool_input):
        return self.run_hook("gate_guard.py", {"tool_name": tool, "tool_input": tool_input})

    def test_issue_creation_blocked_before_gate_3(self):
        cases = [
            ("mcp__github__create_issue", {"title": "T-01 Show when an auction ends"}),
            ("mcp__github__issue_write", {"method": "create"}),
            ("Bash", {"command": "gh issue create --title 'T-01' --body-file t.md --assignee @me"}),
            ("Bash", {"command": "gh api repos/o/r/issues -f title=x"}),
            ("Bash", {"command": "gh api -X POST repos/o/r/issues --input t.json"}),
            ("mcp__claude-in-chrome__navigate", {"url": "https://github.com/o/r/issues/new"}),
            ("mcp__claude-in-chrome__navigate",
             {"url": "https://gitlab.asoft-python.com/tuyen.trantrong/claude-code-training/-/issues/new"}),
            ("mcp__claude-in-chrome__navigate", {"url": "https://gitlab.example.com/a/b/-/work_items/new"}),
            ("mcp__gitlab__create_issue", {"title": "x"}),
            ("Bash", {"command": "glab issue create --title x"}),
            ("Bash", {"command": "curl -X POST https://gitlab.example.com/api/v4/projects/1/issues -d title=x"}),
        ]
        for tool, tool_input in cases:
            with self.subTest(tool=tool, tool_input=tool_input):
                result = self.call(tool, **tool_input)
                self.assertEqual(result.returncode, 2)
                self.assertIn("approve gate 3", result.stderr)

    def test_reading_issues_is_allowed(self):
        for tool, tool_input in [
            ("Bash", {"command": "gh issue list --state open"}),
            ("Bash", {"command": "gh api repos/o/r/issues"}),
            ("Bash", {"command": "gh pr create --base practice --title x --body y"}),
            ("mcp__github__list_issues", {}),
            ("mcp__claude-in-chrome__navigate", {"url": "https://github.com/o/r/issues/4"}),
            ("mcp__claude-in-chrome__navigate", {"url": "https://gitlab.example.com/a/b/-/issues/4"}),
            ("Bash", {"command": "curl https://gitlab.example.com/api/v4/projects/1/issues"}),
            ("Bash", {"command": "git status"}),
        ]:
            with self.subTest(tool=tool, tool_input=tool_input):
                self.assertEqual(self.call(tool, **tool_input).returncode, 0)

    def test_allowed_after_gate_3(self):
        (self.folder / "approvals").mkdir()
        (self.folder / "approvals" / "gate-3.md").write_text("# Gate 3 approved\n", encoding="utf-8")
        self.assertEqual(self.call("Bash", command="glab issue create --title x").returncode, 0)

    def test_no_kickoff_is_not_guarded(self):
        (self.root / "intent" / "CURRENT").unlink()
        self.assertEqual(self.call("Bash", command="glab issue create --title x").returncode, 0)


class PathGuardTest(ProjectTestCase):
    def call(self, tool, agent=None, **tool_input):
        payload = {"tool_name": tool, "tool_input": tool_input}
        if agent:
            payload["agent_type"] = agent
        return self.run_hook("path_guard.py", payload)

    def path(self, rel):
        return str(self.root / rel)

    def test_roles_read_their_files(self):
        for agent, rel in [
            ("dev", f"{FOLDER}/tickets/T-01-show-auction-end.md"),
            ("dev", f"{FOLDER}/spec.md"),
            ("dev", "docs/baseline.md"),
            ("dev", "day-02/auction/bids.py"),
            ("ba", f"{FOLDER}/brief.md"),
            ("ba", f"{FOLDER}/intake.md"),
            ("qa", f"{FOLDER}/tickets/T-01-show-auction-end.md"),
            ("lead", ".kickoff-private/client-truth.md"),
        ]:
            with self.subTest(agent=agent, rel=rel):
                self.assertFalse(self.denied(self.call("Read", agent, file_path=self.path(rel))))

    def test_roles_cannot_read_other_files(self):
        for agent, rel in [
            ("dev", f"{FOLDER}/brief.md"),
            ("dev", f"{FOLDER}/intake.md"),
            ("dev", f"{FOLDER}/test-matrix.md"),
            ("ba", ".kickoff-private/client-truth.md"),
            ("qa", f"{FOLDER}/brief.md"),
            ("qa", f"{FOLDER}/intake.md"),
            ("lead", f"{FOLDER}/spec.md"),
        ]:
            with self.subTest(agent=agent, rel=rel):
                self.assertTrue(self.denied(self.call("Read", agent, file_path=self.path(rel))))

    def test_role_writes(self):
        self.assertFalse(self.denied(self.call("Write", "ba", file_path=self.path(f"{FOLDER}/spec.md"))))
        self.assertFalse(self.denied(self.call("Edit", "qa", file_path=self.path(f"{FOLDER}/test-matrix.md"))))
        self.assertTrue(self.denied(self.call("Write", "qa", file_path=self.path(f"{FOLDER}/spec.md"))))
        self.assertTrue(self.denied(self.call("Write", "dev", file_path=self.path(f"{FOLDER}/tickets/T-01-x-y.md"))))

    def test_roles_have_no_shell(self):
        self.assertTrue(self.denied(self.call("Bash", "ba", command="ls")))

    def test_search_needs_an_allowed_path(self):
        self.assertTrue(self.denied(self.call("Glob", "dev", pattern="**/*.md")))
        self.assertFalse(self.denied(self.call("Glob", "dev", pattern="*.md", path=self.path(f"{FOLDER}/tickets"))))

    def test_nobody_writes_approvals(self):
        approval = self.path(f"{FOLDER}/approvals/gate-1.md")
        self.assertTrue(self.denied(self.call("Write", file_path=approval)))
        self.assertTrue(self.denied(self.call("Write", "ba", file_path=approval)))
        for command in (f"echo yes > {FOLDER}/approvals/gate-1.md",
                        f"cd {FOLDER} && printf x > approvals/gate-2.md",
                        f"mkdir -p {FOLDER}/approvals",
                        f"Set-Content {FOLDER}\\approvals\\gate-3.md yes"):
            with self.subTest(command=command):
                self.assertTrue(self.denied(self.call("Bash", command=command)))

    def test_word_approvals_alone_is_not_a_write(self):
        for command in ("gh api repos/o/r/branches/main/protection --jq '{approvals: .x}' 2>&1",
                        "grep -n approvals .claude/hooks/path_guard.py 2>/dev/null",
                        f"ls {FOLDER}/approvals"):
            with self.subTest(command=command):
                self.assertFalse(self.denied(self.call("Bash", command=command)))

    def test_reviewer_reads_the_repo_but_not_private_notes(self):
        for rel in ("day-11/webapp/server.py", f"{FOLDER}/brief.md", "CLAUDE.md", ".review/x/context.md"):
            with self.subTest(rel=rel):
                self.assertFalse(self.denied(self.call("Read", "reviewer", file_path=self.path(rel))))
        self.set_state("done")  # even after the reveal
        self.assertTrue(self.denied(self.call("Read", "reviewer", file_path=self.path(".kickoff-private/client-truth.md"))))
        self.assertTrue(self.denied(self.call("Grep", "reviewer", pattern="x", path=self.path(".kickoff-private"))))

    def test_reviewer_writes_nothing(self):
        for rel in ("day-11/webapp/server.py", f"{FOLDER}/tickets/T-01-x-y.md", ".review/b/findings.md"):
            with self.subTest(rel=rel):
                self.assertTrue(self.denied(self.call("Write", "reviewer", file_path=self.path(rel))))
        self.assertTrue(self.denied(self.call("Bash", "reviewer", command="git diff")))

    def test_main_conversation_cannot_read_private_notes_before_reveal(self):
        self.assertTrue(self.denied(self.call("Read", file_path=self.path(".kickoff-private/client-truth.md"))))
        self.assertTrue(self.denied(self.call("Bash", command="cat .kickoff-private/client-truth.md")))
        self.set_state("reveal")
        self.assertFalse(self.denied(self.call("Read", file_path=self.path(".kickoff-private/client-truth.md"))))

    def test_main_conversation_works_normally(self):
        self.assertFalse(self.denied(self.call("Read", file_path=self.path("day-02/auction/bids.py"))))
        self.assertFalse(self.denied(self.call("Bash", command="git status")))


class SessionHooksTest(ProjectTestCase):
    def test_session_start_reports_waiting_gate(self):
        out = self.hook_output(self.run_hook("load_state.py", {}))
        self.assertIn("Gate 1", out["additionalContext"])

    def test_statusline(self):
        line = self.run_hook("load_state.py", {}, "--statusline").stdout.strip()
        self.assertEqual(line, "kickoff 2026-11-03-auction-end-time | Gate 1 waiting")
        self.set_state("pack")
        self.assertTrue(self.run_hook("load_state.py", {}, "--statusline").stdout.strip().endswith("next: pack"))

    def test_statusline_without_kickoff(self):
        (self.root / "intent" / "CURRENT").unlink()
        self.assertEqual(self.run_hook("load_state.py", {}, "--statusline").stdout.strip(), "kickoff: none")

    def test_notify_never_fails(self):
        self.set_state("pack")
        self.assertEqual(self.run_hook("notify_gate.py", {}).returncode, 0)

    def test_ba_kept_going_on_bad_ticket(self):
        self.write_ticket(GOOD_TICKET.replace("So that I can bid before it closes\n", ""))
        result = self.run_hook("lint_on_stop.py", {"agent_type": "ba"})
        self.assertEqual(result.returncode, 2)
        self.assertIn("So that", result.stderr)

    def test_ba_may_stop_on_good_ticket(self):
        self.write_ticket()
        self.assertEqual(self.run_hook("lint_on_stop.py", {"agent_type": "ba"}).returncode, 0)

    def test_second_stop_is_allowed(self):
        self.write_ticket(GOOD_TICKET.replace("So that I can bid before it closes\n", ""))
        result = self.run_hook("lint_on_stop.py", {"agent_type": "ba", "stop_hook_active": True})
        self.assertEqual(result.returncode, 0)

    def test_qa_only_answers_for_the_matrix(self):
        self.write_ticket(GOOD_TICKET.replace("So that I can bid before it closes\n", ""))
        self.assertEqual(self.run_hook("lint_on_stop.py", {"agent_type": "qa"}).returncode, 0)

