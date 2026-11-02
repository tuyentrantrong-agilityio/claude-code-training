# T-01 Reject bids below the minimum

Status: ready
Issue: #3
Dev rounds: 1
Spec: [Minimum raise](../spec.md#behaviour)

## Story

As a bidder
I want a too-low bid to be refused with the lowest amount I may offer
So that every raise is meaningful and I know what to bid instead

## Scenarios

### S1 Bid of exactly the minimum under 1000 is accepted

Given auction 7 has a highest bid of 100 by user 5 and no other active bid
When user 42 posts `{"auction_id": 7, "amount": 110}` to `POST /api/bids`
Then the API returns 201 `{"id": n}`
And My bids for user 42 lists the bid of 110 on auction 7 with standing `winning`
And the page form after this accepted bid behaves exactly as it does today (no change to clearing or keeping the fields)
And every existing test that expected `bid must be higher than <highest>` or an accepted raise of 1 now expects the new rule and message; no test is kept for the old rule

### S2 Bid below the minimum is refused with the minimum on API and page

Given auction 7 has a highest bid of 100 by user 5
When user 42 types Auction ID 7 and Amount 109 in the page form and clicks Place bid
Then `POST /api/bids` returns 409 `{"error": "bid must be at least 110"}` and no bid is stored
And the red error line on the page reads "bid must be at least 110"
And the Auction ID field still shows 7 and the Amount field still shows 109

### S3 Step of 10 applies up to a highest bid of 999

Given auction 8 has a highest bid of 999 by user 5
When user 42 bids 1008 and then bids 1009 on auction 8
Then the bid of 1008 gets 409 `{"error": "bid must be at least 1009"}`
And the bid of 1009 gets 201

### S4 Step of 50 applies from a highest bid of 1000

Given auction 9 has a highest bid of 1000 by user 5
When user 42 bids 1049 and then bids 1050 on auction 9
Then the bid of 1049 gets 409 `{"error": "bid must be at least 1050"}`
And the bid of 1050 gets 201

### S5 First bid on an auction is free

Given auction 10 has never had a bid
When user 42 bids 1 on auction 10
Then the API returns 201 and My bids lists the bid of 1 on auction 10 as `winning`

### S6 Invalid amounts are still refused before the minimum check

Given auction 7 has a highest bid of 100 by user 5
When user 42 posts amount 0, then amount 110.5, then no amount
Then each request returns 400 with exactly the same `{"error": ...}` body the server returns for that input today (messages unchanged) and no bid is stored
And the tests assert those existing 400 message strings as they are

## Out of scope

- Raising your own bid, cancelled bids, old bids, simultaneous bids and overflow (T-02).
- Showing the minimum before the bidder tries (T-03).
- Changing the step, per-auction steps, amounts with cents.
- Reporting on final prices.
- Changing the 400 validation messages or what the form does after an accepted bid.

## Questions

- [N] (dev, iter 1) S6 says "the baseline validation error" but the ticket gives no body. Should I keep the exact 400 messages that `day-11/webapp/server.py` returns today for amount 0, 110.5 and a missing amount, and assert those strings in the tests? -> answered in ticket body (iter 1)
- [N] (dev, iter 1) S2 says the fields keep their typed values after a rejection. After an accepted bid, should the form fields clear or keep their values, as the page does today? -> BA decision: keep today's behaviour after an accepted bid, unchanged (S1, Out of scope), because the client only asked about the form after a rejected bid (Q10) and this feature should not change anything else on the page.
- [N] (dev, iter 1) The ticket says old tests are updated, but not which ones. Should I change every existing test that asserts `bid must be higher than` or an accepted +1 raise to the new rule, and add no new tests for old behaviour? -> answered in ticket body (iter 1)
