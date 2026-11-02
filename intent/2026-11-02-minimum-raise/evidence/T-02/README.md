# Evidence: T-02 Apply the minimum to every bid

T-02 needs no production change: the T-01 check (`place_bid`, one SQL statement over
active bids only) already gives every scenario. This ticket adds the tests that prove it.

| File | Shows |
|---|---|
| `tests.txt` | `run_tests.py --save`: 145 tests OK |
| `minimum-raise-tests.txt` | Each test of `day-11/tests/test_minimum_raise.py`, T-01 and T-02 rows, all ok |

## Matrix rows

| Row | Scenario | Test |
|---|---|---|
| M-014 | S1 own raise needs the step | `test_raising_own_bid_needs_the_step` |
| M-015 | S2 cancelled bid ignored | `test_cancelled_bid_is_ignored_for_minimum` |
| M-016 | S3 all cancelled, free bid | `test_all_cancelled_auction_takes_free_bid` |
| M-017 | S4 old bids left alone | `test_old_bids_left_alone_and_next_bid_needs_step` |
| M-018 | S5 two equal bids at once | `test_two_equal_simultaneous_bids_store_one` |
| M-019 | S6 minimum above the max amount | `test_minimum_above_max_amount_is_refused` |
| M-020 to M-026 | edges | cancelled plus step, validation, tie, different simultaneous bids, highest at max, repeated requests |

## How the tests were checked

- Run against `bids.py` from before T-01: 9 of the 13 T-02 tests fail. The other 4
  (cancelled bid ignored, all cancelled is free, validation, different simultaneous bids)
  describe behaviour the baseline already had.
- Run 5 times in a row on the new code: all pass, so the concurrency tests are stable.

## Limits

- No browser run: T-02 changes no page behaviour. Old bids (S4) and a second user are
  stored straight into the server's database, because the web UI has one fixed user (42).
- "At the same moment" means threads released by a `threading.Barrier`; the server
  serialises them with its lock, as in production.
