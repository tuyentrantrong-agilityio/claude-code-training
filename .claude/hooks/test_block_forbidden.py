"""Run from the repo root: python -m unittest discover -s .claude/hooks -v"""

import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from block_forbidden import check  # noqa: E402

BLOCKED = [
    "git push --force origin feat/x",
    "git push -f origin feat/x",
    "git push -fu origin x",
    "git push origin +x",
    "git push --force-with-lease origin x",
    "git push --mirror origin",
    "git push --all origin",
    "git push origin main",
    "git push origin HEAD:practice",
    "git push origin HEAD:refs/heads/main",
    "git push origin :main",
    'git push origin "main"',
    "git -C ../other push --force origin x",
    "git --git-dir .git push --force origin x",
    "git --work-tree . commit --no-verify -m x",
    "git commit --no-verify -m x",
    "git commit -n -m x",
    "rm -rf build",
    "rm -fr ./tmp",
    "rm -Rf build",
    "rm -rfv build",
    "rm -r -f build",
    "rm --recursive --force build",
    "/bin/rm -rf build",
    "sudo rm -rf x",
    "env git push -f origin main",
    "FOO=1 git push --force origin x",
    "(rm -rf x)",
    'bash -c "rm -rf x"',
    "cd x && git push origin main",
    "git status; git push --force",
    "echo it\\'s; git push --force origin x; echo 'y'",
    "cd day-04 &&\ngit push --force origin main",
    "git status;\nrm -rf build",
    "cd x && \\\ngit push --force origin main",
    "git status  # check branch\ngit push --force origin main",
    "echo a#b; rm -rf build",
    "git commit -F - <<EOF && git push --force origin main\nmsg\nEOF",
    "bash <<EOF\nrm -rf x\nEOF",
]

BLOCKED_POWERSHELL = [
    "Remove-Item -Recurse -Force .\\tmp",
    "Remove-Item x -r -fo",
    "Remove-Item .\\build\\ -Recurse -Force",
    "rm .\\tmp\\ -r -fo",
    "ri -Recurse -Force x",
    "del -Recurse -Force x",
    "Remove-Item .\\build `\n    -Recurse -Force",
    "Remove-Item x -Recurse:$true -Force",
    'pwsh -Command "Remove-Item x -Recurse -Force"',
]

ALLOWED = [
    'git push -u origin feat/day-09-hook -o merge_request.target=practice'
    ' -o "merge_request.description=MR into practice, never main."',
    "git push -u origin fix/main-bug",
    "git push origin practice-notes",
    'git commit -m "docs: never push to main or use rm -rf"',
    "git commit -F - <<EOF\nfix: stop rm -rf in cleanup\ngit push origin main is not allowed\nEOF",
    "rm build.log",
    "rm -r build",
    "echo a#b",
    "python -m unittest discover -s tests -t . -v",
    "git push -u origin add-claude-workflow; gh pr create --base main --head add-claude-workflow",
    "git push --dry-run origin feat/x",
    "git status  # no push here",
]

ALLOWED_POWERSHELL = [
    "Remove-Item build.log",
    "Remove-Item .\\build\\ -Recurse",
    'git commit -m "clean up with Remove-Item -Recurse -Force"',
]


def make_repo(branch):
    path = tempfile.mkdtemp()
    subprocess.run(["git", "init", "-q", "-b", branch, path], check=True)
    return path


class CheckTest(unittest.TestCase):
    def setUp(self):
        self.feature_repo = make_repo("feat/x")

    def test_forbidden_commands_are_blocked(self):
        for command in BLOCKED:
            with self.subTest(command=command):
                self.assertIsNotNone(check(command, cwd=self.feature_repo))

    def test_forbidden_powershell_commands_are_blocked(self):
        for command in BLOCKED_POWERSHELL:
            with self.subTest(command=command):
                self.assertIsNotNone(check(command, cwd=self.feature_repo, tool="PowerShell"))

    def test_normal_commands_are_allowed(self):
        for command in ALLOWED:
            with self.subTest(command=command):
                self.assertIsNone(check(command, cwd=self.feature_repo))

    def test_normal_powershell_commands_are_allowed(self):
        for command in ALLOWED_POWERSHELL:
            with self.subTest(command=command):
                self.assertIsNone(check(command, cwd=self.feature_repo, tool="PowerShell"))

    def test_push_head_depends_on_current_branch(self):
        self.assertIsNone(check("git push origin HEAD", cwd=self.feature_repo))
        protected = make_repo("main")
        for command in ("git push origin HEAD", "git push -u origin @", "git push"):
            with self.subTest(command=command):
                self.assertIsNotNone(check(command, cwd=protected))

    def test_unbalanced_quotes_are_blocked(self):
        self.assertIsNotNone(check("echo 'unterminated"))


class MainTest(unittest.TestCase):
    def run_hook(self, stdin):
        script = os.path.join(HERE, "block_forbidden.py")
        return subprocess.run([sys.executable, script], input=stdin,
                              capture_output=True, text=True)

    def test_blocked_command_exits_2(self):
        result = self.run_hook(json.dumps({"tool_input": {"command": "rm -rf x"}}))
        self.assertEqual(result.returncode, 2)

    def test_allowed_command_exits_0(self):
        result = self.run_hook(json.dumps({"tool_input": {"command": "rm x.log"}}))
        self.assertEqual(result.returncode, 0)

    def test_tool_name_selects_powershell_rules(self):
        command = "Remove-Item .\\build\\ -Recurse -Force"
        result = self.run_hook(json.dumps({"tool_name": "PowerShell", "tool_input": {"command": command}}))
        self.assertEqual(result.returncode, 2)

    def test_bad_input_fails_closed(self):
        for stdin in ("not json", '{"tool_input": null, "x": 1'):
            with self.subTest(stdin=stdin):
                self.assertEqual(self.run_hook(stdin).returncode, 2)

    def test_missing_command_is_allowed(self):
        self.assertEqual(self.run_hook('{"tool_input": null}').returncode, 0)


if __name__ == "__main__":
    unittest.main()
