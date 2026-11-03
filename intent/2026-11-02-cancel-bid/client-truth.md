# Client truth: Cancel my bid

Folder: intent/2026-11-02-cancel-bid

## What I really want
Bidders sometimes mistype an amount or bid on the wrong auction and then they write to me in a panic. I want them to take back a bid themselves, without it being abused to game the auction, so support requests drop and bidders trust the site.

## Requirements
- H1 A bidder sees a Cancel button on each of their own active bids in My bids.
- H2 A cancelled bid stays in the list with status `cancelled` and an empty standing (not removed).
- H3 A bidder can cancel only their own bids; trying someone else's bid is refused.
- H4 After a cancel, the highest bid and the minimum next bid of that auction are recalculated from the remaining active bids.
- H5 The bidder must confirm before the cancel happens.
- H6 Cancelling a bid that is already cancelled gives a clear error and changes nothing.
- H7 (hidden) A bid can be cancelled only within 5 minutes of being placed; later the error says it is too late to cancel.
- H8 (hidden) Cancelling a bid never triggers the outbid banner for the bidder (the banner is only for being beaten by someone else).

## "You decide"
- Wording of the confirmation text and of the error messages.
- Look and place of the Cancel button (colour, icon or text).
- What the system answers technically when a bid does not exist.

## Planned contradiction
- Brief says: cancelled bids should simply disappear from the list.
- Later answer says: actually keep them in the list marked as cancelled, so bidders can see their history (H2).

## Not wanted
- Letting the site owner or an admin cancel other people's bids.
- Refunds, emails or notifications about a cancel.
- Undoing a cancel.

## Added during answers
- Any active bid can be cancelled, winning or outbid.
- No limit on number of cancels (the 5 minute rule is enough).
- Nothing special for the owner of a bid that becomes winning again.
- After a cancel the bidder may bid again like any other bid.
- No reason asked; no edit of amounts (cancel and bid again).
- Bids placed before the feature can be cancelled, 5 minute rule still applies.
- Done means: cancel from My bids and the price to beat updates for everyone.
