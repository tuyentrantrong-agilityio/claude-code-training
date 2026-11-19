"""scripts/lint_tickets.py and scripts/score_kickoff.py."""

import sys
import unittest

from tests.helpers import GOOD_TICKET, MATRIX, REPO, ProjectTestCase

sys.path.insert(0, str(REPO / "scripts"))

from check_matrix import check  # noqa: E402
from lint_tickets import lint  # noqa: E402
from release_notes import parse_merges, render as render_notes  # noqa: E402
from review_findings import check as check_findings, counts as findings_counts  # noqa: E402
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

    def ready_after(self, rounds, *questions):
        text = GOOD_TICKET.replace("Status: draft", f"Status: ready\nDev rounds: {rounds}")
        return self.problems(text.replace("- None yet.", "\n".join(questions) or "- None yet."))

    def test_ready_right_after_answering_a_dev_blocker(self):
        # What happened to T-03 in the minimum raise kickoff: the BA answered round 1's
        # [B] questions and set ready without a second Dev read.
        problems = self.ready_after(1, "- [B] (dev, iter 1) Which time zone? -> answered in ticket body (iter 1)")
        self.assertTrue(any("Dev round 1 raised a [B] question" in p for p in problems))

    def test_ready_after_a_clean_dev_round(self):
        self.assertEqual(self.ready_after(1), [])
        self.assertEqual(self.ready_after(
            2,
            "- [B] (dev, iter 1) Which time zone? -> answered in ticket body (iter 1)",
            "- [N] (dev, iter 2) Show seconds? -> BA decision: no seconds, because bidders plan by minute.",
        ), [])

    def test_ready_before_any_dev_round(self):
        self.assertTrue(any("before any Dev round" in p for p in self.ready_after(0)))

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
        self.evidence = self.folder / "evidence" / "T-01"
        self.evidence.mkdir(parents=True)
        (self.evidence / "README.md").write_text("# Evidence: T-01\n", encoding="utf-8")
        (self.tests / "test_end.py").write_text(code, encoding="utf-8")

    def test_evidence_needs_a_readme(self):
        self.build("def test_a(): pass\ndef test_b(): pass\n")
        (self.evidence / "README.md").unlink()
        self.assertEqual(check(self.folder)[0], ["evidence/T-01: no README.md"])

    def test_every_screenshot_is_shown_inline(self):
        self.build("def test_a(): pass\ndef test_b(): pass\n")
        for name in ("01-ok.png", "02-missing.jpg"):
            (self.evidence / name).write_bytes(b"x")
        (self.evidence / "README.md").write_text("![first](01-ok.png)\n02-missing.jpg is listed only\n",
                                                encoding="utf-8")
        self.assertEqual(check(self.folder)[0],
                         ["evidence/T-01: README.md does not show 02-missing.jpg inline (![...](02-missing.jpg))"])

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
        (self.folder / "evidence" / "T-01" / "README.md").write_text("# Evidence\n", encoding="utf-8")
        problems, _ = check(self.folder)
        self.assertEqual(problems, [f"M-00{i}: day-02/tests/test_end.py does not exist" for i in (1, 2)])

    def test_planned_test_must_name_a_function(self):
        self.build("def test_a(): pass\ndef test_b(): pass\n")
        matrix = MATRIX.replace("`day-02/tests/test_end.py::test_b`", "manual check in the browser")
        (self.folder / "test-matrix.md").write_text(matrix, encoding="utf-8")
        problems, _ = check(self.folder)
        self.assertEqual(len(problems), 1)
        self.assertIn("M-002: planned test 'manual check in the browser'", problems[0])


GOOD_FINDINGS = """\
# Review: feat/x

## Findings

- [major] day-11/webapp/server.py:12 The 400 check runs after the lookup. Rule: T-03 S4

## Checked

- T-03 S1 to S6 against the code and tests.
"""


class ReviewFindingsTest(unittest.TestCase):
    def test_good_findings(self):
        self.assertEqual(check_findings(GOOD_FINDINGS), [])
        self.assertEqual(findings_counts(GOOD_FINDINGS), {"blocker": 0, "major": 1, "minor": 0})

    def test_clean_review_still_says_what_was_checked(self):
        clean = GOOD_FINDINGS.replace(
            "- [major] day-11/webapp/server.py:12 The 400 check runs after the lookup. Rule: T-03 S4", "- None.")
        self.assertEqual(check_findings(clean), [])
        self.assertIn("'## Checked' needs at least one line saying what was checked",
                      check_findings(clean.split("## Checked")[0]))

    def test_finding_needs_level_place_and_rule(self):
        for bad in (" Rule: T-03 S4", "[major]", ":12"):
            with self.subTest(removed=bad):
                text = GOOD_FINDINGS.replace(bad, "[huge]" if bad == "[major]" else "")
                self.assertTrue(any("finding not in the form" in p for p in check_findings(text)))

    def test_text_before_the_title_or_non_ascii(self):
        self.assertIn("first line must be '# Review: <branch>'", check_findings("Here it is:\n" + GOOD_FINDINGS))
        self.assertIn("plain ASCII only", check_findings(GOOD_FINDINGS.replace("runs after", "runs " + chr(0x2192) + " after")))


MERGE_LOG = (
    "Merge pull request #13 from me/fix/edges\x1ffix: answer every bad request with json\n\x1e"
    "Merge branch 'wip' into feat/x\x1f\x1e"
    "Merge pull request #12 from me/feat/reviewer\x1ffeat: add a reviewer agent\n\x1e"
    "Merge branch 'feat/kickoff' into 'practice'\x1ffeat: add kickoff harness\n\n"
    "See merge request me/repo!27\n\x1e"
    "Merge pull request #1 from me/odd\x1fMove to GitHub\n\x1e"
)


class ReleaseNotesTest(ProjectTestCase):
    def test_merges_from_github_and_gitlab_oldest_first(self):
        self.assertEqual(parse_merges(MERGE_LOG), [
            {"ref": "#1", "type": "chore", "title": "Move to GitHub"},
            {"ref": "GitLab !27", "type": "feat", "title": "add kickoff harness"},
            {"ref": "#12", "type": "feat", "title": "add a reviewer agent"},
            {"ref": "#13", "type": "fix", "title": "answer every bad request with json"},
        ])

    def test_notes_group_changes_and_list_kickoff_tickets(self):
        self.write_ticket(GOOD_TICKET.replace("Status: draft", "Status: ready\nIssue: #3"))
        (self.folder / "evidence" / "T-01").mkdir(parents=True)
        notes = render_notes("v0.2.0", "v0.1.0", "origin/practice", parse_merges(MERGE_LOG),
                             [self.folder], today="2026-11-02")
        self.assertIn("Range: `v0.1.0..origin/practice`, 4 merged changes.", notes)
        self.assertIn("### Features\n\n- add kickoff harness (GitLab !27)\n- add a reviewer agent (#12)\n", notes)
        self.assertIn("### Fixes\n\n- answer every bad request with json (#13)\n", notes)
        self.assertIn("- T-01 Show when an auction ends: issue #3, built, evidence in `evidence/T-01/`", notes)
        self.assertNotIn("### Docs", notes)

    def test_notes_without_merges_or_kickoffs(self):
        notes = render_notes("v0.2.1", "v0.2.0", "origin/practice", [], [], today="2026-11-03")
        self.assertIn("0 merged changes.", notes)
        self.assertIn("No merged changes in this range.", notes)
        self.assertIn("No kickoff in this range.", notes)
