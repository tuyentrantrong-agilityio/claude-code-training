# Ticket 1: My bids crashes or ignores paging for limit 0 or below

**Component:** `day-02/auction/bids.py`, `list_my_bids`

## Description

`GET /me/bids` passes the client's `limit` straight into the SQL `LIMIT`.
With `limit=0` the call crashes. With a negative `limit` SQLite treats the
value as "no limit", so the whole bid history comes back in one response.

Found by ultrareview on Day 10 and reproduced with five bids for one user:

- `list_my_bids(conn, 42, limit=0)` raises `IndexError: list index out of range`
- `list_my_bids(conn, 42, limit=-1)` returns all 5 bids with `next_cursor = None`

## Expected

- `limit` below 1 raises `ValueError`.
- `limit` above 100 raises `ValueError`, so one page stays bounded.
- Valid limits (1 to 100) behave exactly as today.

## Actual

`limit=0` raises `IndexError`; a negative `limit` returns every bid.

## Notes

- Keep cursor pagination on `(created_at, id)` unchanged.
- Add tests in `day-02/tests/test_bids_pagination.py`; do not change the existing ones.
