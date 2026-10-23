"""Run from the repo root: python -m unittest discover -s .claude/hooks -v"""

import json
import os
import subprocess
import sys
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
    "git push origin main",
    "git push origin HEAD:practice",
    "git push origin HEAD:refs/heads/main",
    "git push origin :main",
    'git push origin "main"',
    "git -C ../other push --force origin x",
    "git commit --no-verify -m x",
    "git commit -n -m x",
    "rm -rf build",
    "rm -fr ./tmp",
    "rm -Rf build",
    "rm -rfv build",
    "rm -r -f build",
    "rm --recursive --force build",
    "Remove-Item -Recurse -Force .\\tmp",
    "Remove-Item x -r -fo",
    "ri -Recurse -Force x",
    "del -Recurse -Force x",
    "cd x && git push origin main",
    "git status; git push --force",
    "echo it\\'s; git push --force origin x; echo 'y'",
]

ALLOWED = [
    'git push -u origin feat/day-09-hook -o merge_request.target=practice'
    ' -o "merge_request.description=MR into practice, never main."',
    "git push -u origin fix/main-bug",
    "git push origin practice-notes",
    'git commit -m "docs: never push to main or use rm -rf"',
    "git commit -F - <<EOF\nfix: stop rm -rf in cleanup\nEOF",
    "rm build.log",
    "rm -r build",
    "Remove-Item build.log",
    "python -m unittest discover -s tests -t . -v",
    "git push -u origin add-claude-workflow; gh pr create --base main --head add-claude-workflow",
    "git push --dry-run origin feat/x",
]


class CheckTest(unittest.TestCase):
    def test_forbidden_commands_are_blocked(self):
        for command in BLOCKED:
            with self.subTest(command=command):
                self.assertIsNotNone(check(command, cwd=HERE))

    def test_normal_commands_are_allowed(self):
        for command in ALLOWED:
            with self.subTest(command=command):
                self.assertIsNone(check(command, cwd=HERE))

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

    def test_bad_input_fails_closed(self):
        for stdin in ("not json", '{"tool_input": null, "x": 1', '{"tool_input": null}'):
            with self.subTest(stdin=stdin):
                result = self.run_hook(stdin)
                expected = 0 if stdin == '{"tool_input": null}' else 2
                self.assertEqual(result.returncode, expected)


if __name__ == "__main__":
    unittest.main()
