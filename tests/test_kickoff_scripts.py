"""scripts/lint_tickets.py and scripts/score_kickoff.py."""

import sys

from tests.helpers import GOOD_TICKET, MATRIX, REPO, ProjectTestCase

sys.path.insert(0, str(REPO / "scripts"))

from check_matrix import check  # noqa: E402
from lint_tickets import lint  # noqa: E402
from score_kickoff import render  # noqa: E402


class LintTicketsTest(ProjectTestCase):
    def problems(self, ticket=GOOD_TICKET, name="T-01-show-auction-end.md"):
        self.write_ticket(ticket, name)
        return lint(self.folder)

    def test_good_ticket_passes(self):
        self.assertEqual(self.problems(), [])

    def test_bad_file_name(self):
        self.assertTrue(any("file name" in p for p in self.problems(name="ticket1.md")))

    def test_missing_story_line(self):
        problems = self.problems(GOOD_TICKET.replace("So that I can bid before it closes\n", ""))
        self.assertTrue(any("So that" in p for p in problems))

    def test_scenario_needs_given_when_then(self):
        problems = self.problems(GOOD_TICKET.replace("When user 42 lists their bids\n", ""))
        self.assertTrue(any("S1: missing a 'When'" in p for p in problems))

    def test_scenarios_must_be_numbered_in_order(self):
        problems = self.problems(GOOD_TICKET.replace("### S2 ", "### S3 "))
        self.assertTrue(any("should be numbered S2" in p for p in problems))

    def test_forbidden_words(self):
        problems = self.problems(GOOD_TICKET.replace("Extending the end time", "TBD extending"))
        self.assertTrue(any("TBD" in p for p in problems))

    def test_question_lines(self):
        ok = GOOD_TICKET.replace("- None yet.", "\n".join([
            "- [B] (qa, iter 0) What if two bids arrive at 18:00:00? -> answered in ticket body (iter 1)",
            "- [N] (dev, iter 1) Show seconds? -> BA decision: no seconds, because bidders plan by minute.",
            "- [B] (dev, iter 2) Which time zone is shown?",
        ]))
        self.assertEqual(self.problems(ok), [])
        for bad in ("- [B] (qa, iter 1) wrong iteration", "- [X] (dev, iter 1) bad tag",
                    "- [B] (dev, iter 1) Q? -> because I said so"):
            with self.subTest(bad=bad):
                self.assertNotEqual(self.problems(GOOD_TICKET.replace("- None yet.", bad)), [])

    def test_ready_with_open_blocking_question(self):
        text = GOOD_TICKET.replace("Status: draft", "Status: ready").replace(
            "- None yet.", "- [B] (dev, iter 1) Which time zone is shown?")
        self.assertTrue(any("blocking question" in p for p in self.problems(text)))

    def test_matrix_coverage(self):
        self.write_ticket()
        (self.folder / "test-matrix.md").write_text(MATRIX, encoding="utf-8")
        self.assertEqual(lint(self.folder), [])
        (self.folder / "test-matrix.md").write_text(MATRIX.replace("| negative |", "| happy |"), encoding="utf-8")
        self.assertTrue(any("no negative row" in p for p in lint(self.folder)))
        (self.folder / "test-matrix.md").write_text(MATRIX.splitlines()[0] + "\n" + MATRIX.splitlines()[2] + "\n",
                                                    encoding="utf-8")
        self.assertTrue(any("T-01 S2 has no row" in p for p in lint(self.folder)))

    def test_intake_needs_client_lines(self):
        (self.folder / "intake.md").write_text(
            "# Intake\n\n## Open questions\n\n### Q1 Ends when?\nWhen?\n- client:\n\n### Q2 Zone?\nWhich?\n",
            encoding="utf-8")
        problems = lint(self.folder)
        self.assertTrue(any("Q2" in p and "client" in p for p in problems))
        self.assertTrue(any("Q1" in p and "has not answered" in p for p in lint(self.folder, answered=True)))


class ScoreKickoffTest(ProjectTestCase):
    def test_ready_rounds_and_totals(self):
        self.write_ticket(GOOD_TICKET.replace("Status: draft", "Status: ready\nDev rounds: 2").replace(
            "- None yet.", "\n".join([
                "- [B] (dev, iter 1) Which time zone? -> answered in ticket body (iter 1)",
                "- [N] (dev, iter 2) Show seconds? -> BA decision: no, because minutes are enough.",
            ])))
        text = render(self.folder)
        self.assertIn("| T-01 | 0 | 1/0 | 0/1 | 0 | round 2 | ready |", text)
        self.assertIn("Ready at round 1: 0/1 (0%)", text)
        self.assertIn("Not revealed yet", text)

    def test_recall(self):
        self.write_ticket()
        (self.folder / "recall.md").write_text("\n".join([
            "| H | Requirement | Hidden | Covered by | Verdict |",
            "|---|---|---|---|---|",
            "| H1 | a | no | T-01 S1 | covered |",
            "| H2 | b | yes | T-01 S2 | partial |",
            "| H3 | c | yes | - | missed |",
            "| H4 | d | added | T-01 S1 | covered |",
        ]) + "\n", encoding="utf-8")
        text = render(self.folder)
        self.assertIn("BA recall: 1.5/3 (50%)", text)
        self.assertIn("Hidden requirements recall: 0.5/2 (25%)", text)
        self.assertIn("Missed: H3", text)


class CheckMatrixTest(ProjectTestCase):
    """MATRIX plans day-02/tests/test_end.py::test_a and ::test_b for T-01."""

    def setUp(self):
        super().setUp()
        self.write_ticket()
        (self.folder / "test-matrix.md").write_text(MATRIX, encoding="utf-8")
        self.tests = self.root / "day-02" / "tests"
        self.tests.mkdir(parents=True)

    def build(self, code):
        (self.folder / "evidence" / "T-01").mkdir(parents=True)
        (self.tests / "test_end.py").write_text(code, encoding="utf-8")

    def test_ticket_not_built_is_not_checked(self):
        problems, summary = check(self.folder)
        self.assertEqual(problems, [])
        self.assertEqual(summary, ["T-01: not built yet (2 rows)"])

    def test_built_ticket_with_every_test(self):
        self.build("class EndTest:\n    def test_a(self): pass\n\ndef test_b(): pass\n")
        self.assertEqual(check(self.folder), ([], ["T-01: 2/2 rows have their test"]))

    def test_missing_test_function(self):
        self.build("def test_a(): pass\n")
        problems, summary = check(self.folder)
        self.assertEqual(problems, ["M-002: day-02/tests/test_end.py has no test_b"])
        self.assertEqual(summary, ["T-01: 1/2 rows have their test"])

    def test_name_in_a_comment_does_not_count(self):
        self.build("def test_a(): pass\n# test_b is planned\n")
        self.assertIn("M-002: day-02/tests/test_end.py has no test_b", check(self.folder)[0])

    def test_missing_test_file(self):
        (self.folder / "evidence" / "T-01").mkdir(parents=True)
        problems, _ = check(self.folder)
        self.assertEqual(problems, [f"M-00{i}: day-02/tests/test_end.py does not exist" for i in (1, 2)])

    def test_planned_test_must_name_a_function(self):
        self.build("def test_a(): pass\ndef test_b(): pass\n")
        matrix = MATRIX.replace("`day-02/tests/test_end.py::test_b`", "manual check in the browser")
        (self.folder / "test-matrix.md").write_text(matrix, encoding="utf-8")
        problems, _ = check(self.folder)
        self.assertEqual(len(problems), 1)
        self.assertIn("M-002: planned test 'manual check in the browser'", problems[0])
