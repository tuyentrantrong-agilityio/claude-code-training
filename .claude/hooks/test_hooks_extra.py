"""Tests for block_secrets, post_edit_check, session_status and git_reminder.

Run: python .claude/hooks/test_hooks_extra.py
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import block_secrets  # noqa: E402
import git_reminder  # noqa: E402
import post_edit_check  # noqa: E402
import pre_push_check  # noqa: E402
import session_status  # noqa: E402

# Built from parts so this file does not look like a leaked secret itself.
FAKE_GITLAB_TOKEN = "glpat-" + "a" * 20
FAKE_AWS_KEY = "AKIA" + "B" * 16
FAKE_PRIVATE_KEY = "-----BEGIN " + "RSA PRIVATE KEY-----"


class BlockSecretsTest(unittest.TestCase):
    def test_env_file_is_blocked(self):
        for path in (".env", "C:\\repo\\.env", "/repo/.env.local", "/repo/.env.production"):
            with self.subTest(path=path):
                self.assertIsNotNone(block_secrets.check_path(path))

    def test_env_example_is_allowed(self):
        self.assertIsNone(block_secrets.check_path("/repo/.env.example"))

    def test_pycache_is_blocked(self):
        self.assertIsNotNone(block_secrets.check_path("/repo/day-02/auction/__pycache__/bids.cpython-314.pyc"))
        self.assertIsNotNone(block_secrets.check_path("/repo/x.pyc"))

    def test_normal_file_is_allowed(self):
        self.assertIsNone(block_secrets.check_path("/repo/day-02/auction/bids.py"))

    def test_secret_content_is_blocked(self):
        for text in (FAKE_GITLAB_TOKEN, FAKE_AWS_KEY, FAKE_PRIVATE_KEY, 'api_key = "abcdefghijklmnop"'):
            with self.subTest(text=text[:12]):
                self.assertIsNotNone(block_secrets.check_content(text))

    def test_plain_content_is_allowed(self):
        self.assertIsNone(block_secrets.check_content("def place_bid(conn, user_id):\n    return 1\n"))
        self.assertIsNone(block_secrets.check_content('token = "short"'))

    def test_check_reads_write_and_edit_inputs(self):
        write = {"tool_input": {"file_path": "/repo/a.py", "content": FAKE_AWS_KEY}}
        edit = {"tool_input": {"file_path": "/repo/a.py", "new_string": FAKE_GITLAB_TOKEN}}
        self.assertIsNotNone(block_secrets.check(write))
        self.assertIsNotNone(block_secrets.check(edit))
        self.assertIsNone(block_secrets.check({"tool_input": {"file_path": "/repo/a.py", "content": "x = 1"}}))


class PostEditCheckTest(unittest.TestCase):
    def write(self, name, text):
        path = os.path.join(self.tmp, name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        return path

    def setUp(self):
        self._dir = tempfile.TemporaryDirectory()
        self.tmp = self._dir.name

    def tearDown(self):
        self._dir.cleanup()

    def test_ascii_text_passes(self):
        self.assertIsNone(post_edit_check.check(self.write("a.md", "plain text\n")))

    def test_em_dash_is_reported_with_line_number(self):
        report = post_edit_check.non_ascii_report("ok\nbad \u2014 here\n")
        self.assertEqual(report, ["line 2: U+2014 EM DASH"])

    def test_non_ascii_file_returns_message(self):
        message = post_edit_check.check(self.write("a.md", "caf\u00e9\n"))
        self.assertIn("non-ASCII", message)
        self.assertIn("line 1", message)

    def test_unknown_extension_is_skipped(self):
        self.assertIsNone(post_edit_check.check(self.write("a.bin", "caf\u00e9")))

    def test_missing_file_is_skipped(self):
        self.assertIsNone(post_edit_check.check(os.path.join(self.tmp, "nope.py")))

    def test_pycache_path_is_skipped(self):
        os.makedirs(os.path.join(self.tmp, "__pycache__"))
        self.assertIsNone(post_edit_check.check(self.write(os.path.join("__pycache__", "a.py"), "caf\u00e9")))

    def test_day_folder_needs_a_tests_directory(self):
        root = os.path.join(self.tmp, "day-77")
        os.makedirs(os.path.join(root, "tests"))
        self.assertEqual(post_edit_check.day_folder(os.path.join(root, "x.py")).replace("\\", "/"),
                         root.replace("\\", "/"))
        os.makedirs(os.path.join(self.tmp, "day-78"))
        self.assertIsNone(post_edit_check.day_folder(os.path.join(self.tmp, "day-78", "x.py")))
        self.assertIsNone(post_edit_check.day_folder(os.path.join(self.tmp, "other", "x.py")))

    def test_failing_day_tests_are_reported(self):
        root = os.path.join(self.tmp, "day-77")
        os.makedirs(os.path.join(root, "tests"))
        self.write(os.path.join("day-77", "tests", "__init__.py"), "")
        self.write(os.path.join("day-77", "tests", "test_fail.py"),
                   "import unittest\nclass T(unittest.TestCase):\n    def test_x(self):\n        self.assertEqual(1, 2)\n")
        path = self.write(os.path.join("day-77", "mod.py"), "x = 1\n")
        message = post_edit_check.check(path)
        self.assertIn("fail after editing", message)

    def test_passing_day_tests_return_nothing(self):
        root = os.path.join(self.tmp, "day-77")
        os.makedirs(os.path.join(root, "tests"))
        self.write(os.path.join("day-77", "tests", "__init__.py"), "")
        self.write(os.path.join("day-77", "tests", "test_ok.py"),
                   "import unittest\nclass T(unittest.TestCase):\n    def test_x(self):\n        self.assertEqual(1, 1)\n")
        path = self.write(os.path.join("day-77", "mod.py"), "x = 1\n")
        self.assertIsNone(post_edit_check.check(path))


class SessionStatusTest(unittest.TestCase):
    def test_status_lists_branch_counts_and_dirty_files(self):
        text = session_status.build_status("feat/x", (2, 1), 3)
        self.assertIn("branch feat/x", text)
        self.assertIn("2 commit(s) ahead and 1 behind", text)
        self.assertIn("3 uncommitted", text)
        self.assertNotIn("WARNING", text)

    def test_warning_on_protected_branches(self):
        for branch in ("main", "practice"):
            self.assertIn("WARNING", session_status.build_status(branch, None, 0))

    def test_status_without_upstream_counts(self):
        self.assertNotIn("ahead", session_status.build_status("feat/x", None, 0))


class GitReminderTest(unittest.TestCase):
    def test_git_prompts_get_the_reminder(self):
        for prompt in ("please commit this", "push it", "open a merge request", "Tag v0.2.0", "create a branch"):
            with self.subTest(prompt=prompt):
                self.assertIn("CLAUDE.md", git_reminder.reminder_for(prompt))

    def test_other_prompts_get_nothing(self):
        for prompt in ("explain bids.py", "run the tests", "", None):
            with self.subTest(prompt=prompt):
                self.assertEqual(git_reminder.reminder_for(prompt), "")


class PrePushCheckTest(unittest.TestCase):
    FAIL = "[PASS] commit messages\n[FAIL] no non-ASCII in added lines\n       tests/x.py: U+2192\n"

    def decide(self, command, code=1, branch="feat/x"):
        calls = []

        def checklist(root):
            calls.append(root)
            return code, self.FAIL if code else "[PASS] all\n"

        return pre_push_check.decide(command, "/repo", branch=branch, checklist=checklist), calls

    def test_failing_checklist_blocks_a_branch_push(self):
        for command in ("git push -u origin feat/x", "git push", "git -C /repo push origin HEAD",
                        "git add x && git commit -m 'feat: x' && git push -u origin feat/x 2>&1 | tail -1"):
            with self.subTest(command=command):
                reason, calls = self.decide(command)
                self.assertIn("U+2192", reason)
                self.assertEqual(len(calls), 1)

    def test_passing_checklist_lets_the_push_run(self):
        self.assertEqual(self.decide("git push -u origin feat/x", code=0)[0], None)

    def test_tag_pushes_and_other_commands_are_not_checked(self):
        for command in ("git push origin v0.2.0", "git push --tags", "git status", "gh pr create --base practice",
                        "echo git pushes are checked"):
            with self.subTest(command=command):
                self.assertEqual(self.decide(command), (None, []))

    def test_on_main_or_practice_block_forbidden_decides(self):
        self.assertEqual(self.decide("git push", branch="practice"), (None, []))


if __name__ == "__main__":
    unittest.main()
