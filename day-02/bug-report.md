# Bug: `GET /me/bids` cursor pagination skips bids created in the same millisecond

**Component:** `auction/bids.py` → `list_my_bids()`
**Severity:** Medium: data silently missing from the list, no error shown
**Failing test:** `tests/test_bids_pagination.py::CursorPaginationTest::test_same_millisecond_bids_are_not_skipped`

## Environment

- OS: Windows 10 Pro 10.0.19045
- Python 3.14.2 (stdlib only: `sqlite3`, `unittest`; no dependencies to install)
- Branch `practice`, folder `day-02/`

## Steps to reproduce

From a clean clone:

```bash
git clone git@gitlab.asoft-python.com:tuyen.trantrong/claude-code-training.git
cd claude-code-training
git checkout practice
cd day-02
python -m auction.demo
```

What the demo does (data used):

| id | auction_id | created_at (epoch ms) |
|---|---|---|
| 1 | 1 | 1760000000000 |
| 2 | 2 | 1760000000005 |
| 3 | 3 | 1760000000005 |
| 4 | 4 | 1760000000005 |
| 5 | 5 | 1760000000010 |

Then it walks `list_my_bids(user_id=42, limit=2)` page by page, following `next_cursor` until it is `None`.

## Expected

All 5 bids are returned across pages, each exactly once.

## Actual

```
page 1: ids=[5, 2] next_cursor=eyJjcmVhdGVkX2F0IjogMTc2MDAwMDAwMDAwNX0=
page 2: ids=[1] next_cursor=None
total in DB: 5, returned: 3, missing ids: [3, 4]
```

Bids 3 and 4 are never returned. No error is raised.

Test run (`python -m unittest discover -s tests -t . -v`):

```
FAIL: test_same_millisecond_bids_are_not_skipped
AssertionError: 3 != 5 : got [5, 2, 1]
Ran 3 tests ... FAILED (failures=1)
```

## Relevant code

```python
if cursor is not None:
    sql += " AND created_at < ?"
    params.append(decode_cursor(cursor))          # cursor = created_at only
sql += " ORDER BY created_at DESC LIMIT ?"
...
next_cursor = encode_cursor(items[-1]["created_at"]) if len(items) == limit else None
```

## Hypotheses, each checked with a real run

| # | Hypothesis | How checked | Result | Verdict |
|---|---|---|---|---|
| H1 | Cursor only holds `created_at` and the next page uses strict `<`, so the other rows sharing the last row's millisecond are excluded | Switched to `<=` | `[5, 4, 4, 3, 4, 3, …]`: duplicates plus an **infinite loop** when ties exceed `limit` | **Confirmed root cause.** `<` skips rows and `<=` repeats them. A cursor of `created_at` alone can't point between tied rows. |
| H2 | Off-by-one in `limit` / `next_cursor` (stops one page early) | Same data with distinct timestamps | `[5, 4, 3, 2, 1]`, all returned | Rejected |
| H3 | Cursor encode/decode loses precision (float, truncation to seconds) | Compared last `created_at` with decoded cursor | `1760000000005` == `1760000000005` | Rejected |
| H4 | `ORDER BY created_at` is nondeterministic for ties | Added `id DESC` tiebreak, kept `<` | `[5, 4, 1]`, still missing 2 and 3 | Contributing (it decides *which* tied rows go missing), not the root cause |

## Suggested fix (verified in a scratch run, not applied yet)

Keyset pagination on a unique, ordered key:

```sql
... WHERE user_id = ? AND (created_at, id) < (?, ?)
ORDER BY created_at DESC, id DESC
LIMIT ?
```

with the cursor encoding `{"created_at": ..., "id": ...}` of the last item. Scratch run result: `[5, 4, 3, 2, 1]`.
Old cursors (containing only `created_at`) need a compatibility path, or must be rejected with 400.
