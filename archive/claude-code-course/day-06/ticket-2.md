# Ticket 2: Stale BUG comment in the pagination test

**Component:** `day-02/tests/test_bids_pagination.py`,
`test_same_millisecond_bids_are_not_skipped`

## Description

The test still starts with a `# BUG:` comment saying the cursor only keeps
`created_at` and the next page uses `<`. That bug was fixed on Day 03: the
cursor now keeps `(created_at, id)` and the test passes. The comment now
describes code that no longer exists.

## Expected

Replace the two comment lines with one short line that says what the test
checks (bids that share a millisecond across a page boundary are all returned).

## Notes

- Do not change any test logic or assertions.
- All 4 tests in `day-02/` must still pass.
