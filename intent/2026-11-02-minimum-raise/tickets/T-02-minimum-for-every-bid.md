# T-02 Apply the minimum to every bid

Status: ready
Issue: #4
Dev rounds: 1
Spec: [Minimum raise](../spec.md#behaviour)

## Story

As a bidder
I want the minimum raise to count only bids that still count and to apply to everyone the same way
So that the rule is fair and old auctions keep working

## Scenarios

### S1 Raising your own winning bid also needs the step

Given auction 7 has a highest bid of 100 by user 42
When user 42 bids 105 on auction 7
Then the API returns 409 `{"error": "bid must be at least 110"}`
And My bids still lists the bid of 100 on auction 7 as `winning` and no bid of 105

### S2 Cancelled bids are ignored when computing the minimum

Given auction 11 has an active bid of 100 by user 5 and a cancelled bid of 500 by user 6
When user 42 bids 110 on auction 11
Then the API returns 201 and My bids lists the bid of 110 on auction 11 as `winning`

### S3 Auction whose bids are all cancelled takes a free bid again

Given auction 12 has only one bid, 300 by user 5, with status `cancelled`
When user 42 bids 1 on auction 12
Then the API returns 201 and My bids lists the bid of 1 on auction 12 as `winning`

### S4 Bids placed before the change are left alone

Given auction 13 has bids stored before the change: 100 by user 5, then 101 by user 42, both active
When user 42 loads My bids and user 5 then bids 110 and 111 on auction 13
Then My bids first lists the bid of 101 on auction 13 as `winning`, with its stored row unchanged
And the bid of 110 gets 409 `{"error": "bid must be at least 111"}` and the bid of 111 gets 201

### S5 Two equal bids at the same moment

Given auction 14 has a highest bid of 100 by user 5
When user 42 and user 6 each post a bid of 110 on auction 14 at the same moment
Then exactly one request returns 201 and the other returns 409 `{"error": "bid must be at least 120"}`
And auction 14 has exactly one stored bid of 110

### S6 Minimum above the largest allowed amount

Given auction 15 has a highest bid of 9223372036854775800 by user 5
When user 42 bids 9223372036854775807 on auction 15
Then the API returns 409 `{"error": "bid must be at least 9223372036854775850"}` and no bid is stored

## Out of scope

- Re-checking, cancelling or flagging old bids that raised by less than the step.
- A way to cancel bids (cancelled bids exist only in the data, as in the baseline).
- Showing the minimum in the page form (T-03).

## Questions

- None yet.
