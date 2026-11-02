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
- New behaviour gets a new test. Never edit an existing assertion to make it pass;
  fix the code, unless the test itself is wrong, and then say why in the MR.
- A bug fix starts with a test that fails on the old code.
- Concurrency tests use a file database and a `threading.Barrier` with a timeout,
  so a failing thread cannot hang the run.
- Tests do not touch the network or a real port other than port 0
  (`make_server(0)` picks a free one).
