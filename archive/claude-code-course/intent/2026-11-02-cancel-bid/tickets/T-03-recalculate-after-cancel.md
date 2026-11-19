# T-03 Recalculate the auction after a cancel

Status: ready
Issue: #26
Dev rounds: 1
Spec: [Cancel a bid](../spec.md#what-a-cancel-changes)

## Story

As a bidder
I want an auction to carry on as if a cancelled bid had never been placed
So that the price to beat stays fair for everyone else

## Scenarios

All bids below were placed less than 5 minutes before the cancel.

After a cancel, the baseline rules apply unchanged to the remaining active bids:
highest bid by largest amount, then earliest `created_at`, then lowest `id`; minimum
step 10 while the highest amount is under 1000 and 50 from 1000. For example, if
bid 90 of 100 by user 5 and bid 91 of 100 by user 42 are both active (stored directly
in a test) and bid 90 is cancelled, bid 91 becomes the highest bid and `winning`.

### S1 Cancelling the highest bid restores the previous price

Given auction 7 has bid 30 of 100 by user 5 and bid 31 of 500 by user 42, both active
When user 42 cancels bid 31 and then `GET /api/auctions/7/minimum-bid` is sent
Then the lookup returns 200 `{"auction_id": 7, "highest": 100, "step": 10, "minimum_bid": 110}`
And `highest_bid(conn, 7)` returns the bid with id 30 and amount 100 (asserting on id and amount is enough), and `list_my_bids` for user 5 lists bid 30 as `winning`

### S2 Cancelling an outbid bid leaves the price as it was

Given auction 8 has bid 50 of 100 by user 42 and bid 51 of 200 by user 5, both active
When user 42 cancels bid 50
Then the API returns 200 and `GET /api/auctions/8/minimum-bid` returns `{"auction_id": 8, "highest": 200, "step": 10, "minimum_bid": 210}`
And `list_my_bids` for user 5 still lists bid 51 as `winning`

### S3 An earlier own bid becomes winning again

Given auction 9 has bid 60 of 100 then bid 61 of 150, both by user 42 and active
When user 42 cancels bid 61 and loads `GET /api/bids`
Then bid 61 is listed with `"status": "cancelled"`, `"standing": null`, and bid 60 with `"status": "active"`, `"standing": "winning"`
And `GET /api/auctions/9/minimum-bid` returns `"minimum_bid": 110`

### S4 Bidding again on the same auction after a cancel

Given auction 7 has bid 30 of 100 by user 5 and user 42 has just cancelled bid 31 of 500
When user 42 posts `{"auction_id": 7, "amount": 150}` and then `{"auction_id": 7, "amount": 500}`
Then both answer 201
And `GET /api/bids` lists the bid of 500 as `winning`, the bid of 150 as `outbid` and bid 31 as `cancelled` with standing null

### S5 Cancelling the only active bid frees the auction

Given auction 12 has only bid 70 of 300 by user 42, active
When user 42 cancels bid 70
Then `GET /api/auctions/12/minimum-bid` returns `{"auction_id": 12, "highest": null, "step": null, "minimum_bid": 1}`
And a bid of 1 by user 5 on auction 12 is then accepted (201)

### S6 The step follows the new highest bid and lower bids are refused

Given auction 13 has bid 80 of 990 by user 5 and bid 81 of 1000 by user 42, both active
When user 42 cancels bid 81 and then `GET /api/auctions/13/minimum-bid` is sent
Then the lookup returns 200 `{"auction_id": 13, "highest": 990, "step": 10, "minimum_bid": 1000}`
And a post of `{"auction_id": 13, "amount": 995}` by user 42 returns 409 `{"error": "bid must be at least 1000"}` and no bid is stored

## Out of scope

- A message or banner to a bidder whose bid becomes winning again (nothing special happens).
- Live updates for other bidders: they see the new values on their next request.
- Storing any recalculated value: highest bid, standing and minimum next bid stay computed from active bids.

## Questions

- [N] (dev, iter 1) Scenarios S1 to S6 don't cover equal-amount ties after a cancel (for example 100 by user 5 then 100 by user 42, and the earlier one is cancelled). I would rely on the baseline tie rule (earliest created_at, then lowest id) and add a test for it. Is that right? -> answered in ticket body (iter 1)
- [N] (dev, iter 1) The highest_bid(conn, 7) check in S1 doesn't say what it returns, and I would have to read bids.py to see the shape. I would assert on the bid's id and amount only. Is that enough? -> answered in ticket body (iter 1)
- [N] (dev, iter 1) A cancel can lower the step. For example, with a cancelled 1000 bid over an active 990 bid, the step goes from 50 to 10 and the minimum next bid becomes 1000. I would add a test for it. Is that wanted, or is it out of scope? -> answered in ticket body (iter 1)
