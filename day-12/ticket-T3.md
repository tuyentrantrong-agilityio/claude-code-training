# T3: Reject bids that do not beat the highest bid

**Component:** `day-02/auction/bids.py`, `place_bid`; `day-11/webapp/server.py`
**Spec:** 02-spec.md, behaviour 3

## Story

As the auction owner, I want bids that do not beat the current highest to be
rejected, so that nobody places a silly bid.

## Acceptance criteria

- Given auction 7 has a highest bid of 150, when a user bids 150 or less, then
  the bid is rejected and nothing is stored.
- Given auction 7 has a highest bid of 150, when a user bids 151, then the bid
  is stored.
- Given auction 9 has no bids, when a user bids 1, then the bid is stored.
- Given a rejected bid via `POST /api/bids`, then the response is an error whose
  message states the current highest amount.
- Existing 400 validation (non-integer, non-positive) is unchanged.

## Open questions

- Q5 (BA): can a user outbid themselves? Open.
- Q7 (BA): HTTP status and exact message for a rejection? Open.
- Existing tests call `place_bid` directly with arbitrary amounts. Must they
  keep passing unchanged? Open.

## Dev questions (write here)

(none yet)

## Decisions taken while implementing (dev, to confirm with BA)

- Q5: a user may outbid themselves (the rule only compares to the highest amount).
- Q7: HTTP 409, message "bid must be higher than <highest>".
- Existing tests all use one bid per auction, so they pass unchanged.
- Tests: day-02/tests/test_bid_standing.py, day-11/tests/test_server.py.
