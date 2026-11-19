# QA review of the test code (played by Claude)

Files read: day-02/tests/test_bid_standing.py, day-02/tests/test_bid_race.py,
day-11/tests/test_index_html.py.

## Comments

1. **test_bid_race.py: a failing thread can hang the test.**
   All 20 threads wait on `barrier.wait()` after `connect(self.path)`. If one
   thread fails before the barrier, the other 19 wait forever and the run never
   ends. Suggest `threading.Barrier(20, timeout=10)` so the test fails fast.

2. **test_bid_race.py: it proves "one row", not "the right row".**
   The test only counts 1 ok, 19 rejected and 1 stored row. It does not check
   the stored amount, and it only tries the same amount. Suggest a second test
   with different amounts (for example 100 to 119 at once) and assert the
   stored highest bid equals the maximum.

3. **test_bid_standing.py: CursorTest hides which cursor failed.**
   Six bad cursors are checked in one loop. When one fails, the message does
   not say which. Use `with self.subTest(cursor=cursor):`. Also move the
   `import base64, json` to the top of the file and split the long tuple line.

4. **test_index_html.py: string checks can pass on dead code.**
   `assertIn('"Winning"', html)` also passes if the text is only in a comment
   or an unused variable. It does not show the column renders or the banner
   appears. Keep the tests but say in the test name or docstring that they are
   markup-only, and keep the manual browser check as the real proof for T2 and T4.

5. **test_bid_standing.py: test_equal_amount_earlier_wins inserts by raw SQL.**
   It depends on column names and on the default `status` being 'active'. If
   the schema changes, this test breaks for a reason unrelated to standing.
   Suggest a small helper in the test file that inserts a bid, so the SQL is
   in one place.

6. **Missing case: standing with three or more bidders on one auction.**
   Current tests use two users. Add one case with three bids so that
   winning, outbid and outbid are all checked in a single listing.

## Verdict

Tests are readable and cover the acceptance criteria of T1 to T3. Comments 1
and 3 are small and worth fixing; 2 and 6 add coverage; 4 and 5 are
maintenance notes.
