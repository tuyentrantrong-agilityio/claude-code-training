---
paths:
  - "day-*/tests/**"
  - ".claude/**/test_*.py"
---

# Tests

- `unittest` from the standard library only. No pytest, no third-party packages.
- Run a day's suite from its folder: `cd day-NN && python -m unittest discover -s tests -t . -v`.
  Run everything with `python .claude/skills/run-tests/run_tests.py`.
- Name a test after the behaviour it proves: `test_low_bid_is_rejected_with_409`,
  not `test_case_3`. Use `subTest` when one test loops over several inputs.
- Assert the whole answer the matrix row names: status and body, as literal values
  (`(409, {"error": "bid must be at least 110"})`). A status alone, or one live answer
  compared with another, passes when both are wrong (reviews of PR #9 and #13).
- No comments that record review history in tests; that history lives in `evidence/`.
- New behaviour gets a new test. Never edit an existing assertion to make it pass;
  fix the code, unless the test itself is wrong, and then say why in the PR.
- A bug fix starts with a test that fails on the old code.
- Concurrency tests use a file database and a `threading.Barrier` with a timeout,
  so a failing thread cannot hang the run.
- Page JavaScript is tested by running the page's own `<script>` in Node with a fake DOM
  and fetch (`day-11/tests/js/hint_harness.js`, driven from `test_minimum_hint.py`).
  Node is a tool on the machine, not a package: those tests skip when `node` is missing.
- Tests do not touch the network or a real port other than port 0
  (`make_server(0)` picks a free one).
