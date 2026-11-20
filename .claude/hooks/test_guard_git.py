import unittest

from guard_git import check


class GuardGitTest(unittest.TestCase):
    def test_blocks_push_to_protected_branches(self) -> None:
        for cmd in ("git push origin recapz-practice", "git push -u origin main",
                    "git push origin HEAD:practice"):
            self.assertIsNotNone(check(cmd), cmd)

    def test_blocks_force_push(self) -> None:
        self.assertIsNotNone(check("git push -f origin feat/x"))
        self.assertIsNotNone(check("git push --force-with-lease origin feat/x"))

    def test_allows_feature_push(self) -> None:
        self.assertIsNone(check("git push -u origin feat/recapz-practice-docs"))
        self.assertIsNone(check("git push -u origin feat/db-foundation"))

    def test_blocks_ai_credit_in_commit(self) -> None:
        self.assertIsNotNone(check('git commit -m "x" -m "Co-Authored-By: someone"'))
        self.assertIsNone(check('git commit -m "feat: add the job runner"'))


if __name__ == "__main__":
    unittest.main()
