# Client truth: Minimum raise per bid

Folder: intent/2026-11-02-minimum-raise

## What I really want
Bidders stop raising by 1 and flooding auctions with tiny bids. Each new bid must beat the current top bid by a sensible minimum step, so auctions move faster and look more serious.

## Requirements
- H1 A bid on an auction that already has an active bid must be at least the highest active amount plus the minimum raise.
- H2 The first bid on an auction may still be any amount of 1 or more.
- H3 The minimum raise is 10 when the highest amount is under 1000, and 50 when it is 1000 or more.
- H4 A rejected bid says what the lowest allowed amount is (for example "bid must be at least 60").
- H5 The bid form shows the lowest allowed amount for the auction the bidder typed.
- H6 The web API rejects a too-small bid with the same 409 and the same message.
- H7 (hidden) A bid of exactly the highest plus the minimum raise is accepted.
- H8 (hidden) The step is decided by the current highest amount, not by the amount the bidder offers.

## "You decide"
- Wording and colour of the hint on the form.
- Whether the lowest allowed amount is also returned in the auction listing.
- What the form hint shows for an auction with no bids yet.

## Planned contradiction
- Brief says: the minimum raise is a flat 5 on every auction.
- Later answer says: no, 10 below 1000 and 50 from 1000 up (tiered).

## Not wanted
- Different raise per auction chosen by the seller.
- Automatic bidding (proxy bids).
- Changing or cancelling bids already placed.

## Added during answers
- Raising your own winning bid follows the same rule as everyone.
- Cancelled bids are ignored; if all are cancelled the next bid is free.
- Old bids stay as they are.
- Whole euros only.
- Typed amount stays in the form after a rejection.
- Done = website and API enforce the rule; no reporting.
