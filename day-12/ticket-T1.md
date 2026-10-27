# T1: Show bid standing (winning / outbid) in list_my_bids

**Component:** `day-02/auction/bids.py`, `list_my_bids`
**Spec:** 02-spec.md, behaviour 1 and 4

## Story

As a bidder, I want each of my bids to say if it is the highest on its auction,
so that I know at a glance if I am winning.

## Acceptance criteria

- Given user 42 has the highest bid on auction 7, when listing bids, then that
  item has `standing = "winning"`.
- Given user 42 bid 100 and user 5 later bid 150 on auction 7, then user 42's
  bid has `standing = "outbid"`.
- Given two bids with equal top amount on one auction, then the earlier one
  (lower created_at, then lower id) is `winning`, the other `outbid`.
- Given a user has two bids on one auction, then only the higher one can be
  `winning`; the lower one is `outbid`.
- Given limit and cursor are used, then paging order and next_cursor are
  unchanged, and standing is computed over all bids of the auction, not only
  the current page.

## Open questions

- Q6 (BA): are bids with a status other than 'active' ignored when finding the
  highest bid?

## Dev questions (write here)

(none yet)

## Decisions taken while implementing (dev, to confirm with BA)

- Q6: only bids with status 'active' count when finding the highest bid; a
  non-active bid is shown as `outbid`.
- Tests: day-02/tests/test_bid_standing.py (new file, existing tests untouched).
