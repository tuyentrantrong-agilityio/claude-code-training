"""Tests for check_branch. Run: python .claude/skills/review-checklist/test_check_branch.py"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import check_branch  # noqa: E402


class SubjectTest(unittest.TestCase):
    def test_good_subjects(self):
        for subject in ("feat: add rag compulsory security notebook", "fix: close hook bypasses",
                        "docs: add day 15 demo script", "chore: x1"):
            with self.subTest(subject=subject):
                self.assertIsNone(check_branch.check_subject(subject))

    def test_bad_format(self):
        for subject in ("Add feature", "feat: Add feature", "feat: add feature.", "feature: add x",
                        "feat:add x", "fix:", "feat: "):
            with self.subTest(subject=subject):
                self.assertIsNotNone(check_branch.check_subject(subject))

    def test_ai_mention_in_subject(self):
        self.assertIn("AI or Claude", check_branch.check_subject("docs: add evidence captured by claude"))

    def test_ai_mention_in_body(self):
        self.assertIsNotNone(check_branch.check_body("Co-Authored-By: Someone <a@b.c>"))
        self.assertIsNotNone(check_branch.check_body("Generated with a tool"))
        self.assertIsNone(check_branch.check_body("Explains why the cursor is validated."))


class PathAndDiffTest(unittest.TestCase):
    def test_forbidden_paths(self):
        paths = ["day-02/auction/__pycache__/x.pyc", ".env", "app/.env.local", "a.pyc", ".env.example", "day-02/a.py"]
        self.assertEqual(check_branch.forbidden_paths(paths), paths[:4])

    def test_added_non_ascii_lines_only(self):
        diff = "\n".join([
            "+++ b/a.md",
            "+plain line",
            "+bad \u2014 line",
            "-removed \u2014 line",
            "+++ b/b.md",
            "+caf\u00e9",
        ])
        self.assertEqual(check_branch.added_non_ascii(diff), ["a.md: U+2014", "b.md: U+00E9"])


if __name__ == "__main__":
    unittest.main()
