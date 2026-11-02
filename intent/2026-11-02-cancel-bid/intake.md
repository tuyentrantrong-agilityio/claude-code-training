# Intake: Cancel a bid

Brief: [brief.md](brief.md)

## Requirements
- R1 A bidder can cancel a bid themselves, from the "My bids" page, without contacting support (brief: "cancel one of their own bids themselves")
- R2 A bidder can cancel only their own bids; a bid of another user cannot be cancelled by them (brief: "one of their own bids")
- R3 One action cancels exactly one bid (brief: "cancel one of their own bids")
- R4 A cancelled bid no longer appears in the bidder's "My bids" list (brief: "it should just disappear from their list")
- R5 After a cancel, the highest bid, standing and minimum next bid of that auction are computed as if the cancelled bid had never been placed (brief: "carry on as if that bid had never been placed")
- R6 Other bidders on that auction see the recalculated highest bid and minimum next bid right after the cancel (brief: "price to beat stays fair for everyone else")

## Assumptions
- A1 Any of the bidder's active bids can be cancelled, whether winning or outbid: confirm in Q1
- A2 There is no time limit on cancelling a bid: confirm in Q2
- A3 There is no limit on how many bids a bidder may cancel: confirm in Q3
- A4 The bidder is asked to confirm before the bid is cancelled, and there is no undo: confirm in Q4
- A5 When the cancelled bid was the highest, the next highest active bid becomes winning again, and its owner gets no message beyond the normal standing in their list: confirm in Q5
- A6 The cancelled bid is hidden everywhere in the UI; the bidder has no way to see cancelled bids: confirm in Q6
- A7 After cancelling, the bidder may bid again on the same auction, with the minimum next bid as recalculated: confirm in Q7
- A8 The bidder sees a short confirmation line after a cancel, and an error line if the bid cannot be cancelled: confirm in Q8
- A9 No reason for cancelling is asked: confirm in Q9
- A10 Changing the amount of a bid (edit) is not part of this feature; the bidder cancels and bids again: confirm in Q10
- A11 Cancelling a bid does not trigger the outbid banner for anyone, including a bidder who becomes winning again or stays outbid: confirm in Q11
- A12 Bids placed before this feature can be cancelled like new ones: confirm in Q12

## Conflicts with the baseline
- Baseline "My bids" (`list_my_bids`) lists all of the user's bids, including non-active ones with standing `null`. The brief wants cancelled bids to disappear from the list. The spec will change "My bids" to leave out cancelled bids (see Q6 for whether any other non-active bids exist or should still show).
- Baseline has no way to change a bid's status from the web app or API; cancelling adds a new action on top of it. The `cancelled` status value already exists in the data rules and already stops a bid counting for the highest bid, so R5 fits the baseline rules.

## Open questions
### Q1 Which bids can be cancelled
Can a bidder cancel any of their own bids, or only some of them? Options: (a) any active bid, winning or outbid; (b) only a bid that is currently winning; (c) only a bid that is outbid (so cancelling never lowers the price for others).
- client: (a) any active bid of their own, winning or outbid.

### Q2 Time limit on cancelling
Is there a time limit after placing a bid? Options: (a) no limit, a bid can be cancelled at any time; (b) only within a few minutes of placing it (please say how many); (c) only until someone else bids higher on that auction.
- client: (b) only within 5 minutes of placing it. After that the bidder gets a message saying it is too late to cancel.

### Q3 Limit on how many cancels
Should there be a limit to stop abuse, for example a bidder placing and cancelling high bids to scare others off? Options: (a) no limit; (b) at most N cancels per bidder per day (please give N); (c) at most one cancel per auction per bidder.
- client: (a) no limit for now. The 5 minutes should be enough.

### Q4 Confirm and undo
What happens when the bidder clicks cancel? Options: (a) a "Cancel this bid?" confirmation first, then the bid is gone for good; (b) cancelled at once, with no confirmation and no undo; (c) cancelled at once with a short "Undo" option.
- client: (a) ask them to confirm first. No undo after that.

### Q5 When the cancelled bid was winning
If the cancelled bid was the highest bid, the next highest bid on that auction becomes the highest again. Should its owner be told in any way, or do they just see "winning" in their list next time they look? Options: (a) nothing special, they just see "winning" again; (b) a banner such as "You are winning again on auction N".
- client: (a) nothing special.

### Q6 Seeing cancelled bids later
The brief says a cancelled bid disappears from the bidder's list. Should the bidder be able to see their cancelled bids anywhere at all? Options: (a) no, it is gone for good from what they see; (b) a separate "Show cancelled" option on the page; (c) it stays in the list but greyed out with status "cancelled".
- client: Actually, (c). Keep it in the list marked "cancelled" with no standing, so bidders can see their history. Forget what I wrote in the brief.

### Q7 Bidding again after a cancel
After cancelling a bid on an auction, can the same bidder bid on that auction again, including the same amount if it is still allowed? Options: (a) yes, like any other bid; (b) no, they are blocked from that auction; (c) yes, but not for some time.
- client: (a) yes, like any other bid.

### Q8 What the bidder sees after a cancel
After a cancel, what should the bidder see? Options: (a) the bid leaves the list and a line such as "Bid N on auction M cancelled"; (b) the bid just leaves the list, no message. And if the cancel fails (for example the bid was already cancelled in another tab), is a red error line such as "This bid can no longer be cancelled" fine?
- client: you decide

### Q9 Reason for cancelling
Should the bidder give a reason (wrong amount, wrong auction, other) when cancelling? Options: (a) no reason asked; (b) an optional reason; (c) a required reason.
- client: (a) no reason asked.

### Q10 Changing a bid instead of cancelling
For a wrong amount, do bidders also need to change the amount of a bid directly, or is "cancel, then bid again" enough for now? Options: (a) cancel and bid again is enough; (b) they also need to edit the amount.
- client: (a) cancel and bid again is enough.

### Q11 Outbid banner after a cancel
Today a bidder sees "You were outbid on auction N" when a bid that was winning is now beaten. A cancel can change who is winning. Should a cancel ever make that banner appear, for the bidder who cancelled or for anyone else? Options: (a) never because of a cancel; (b) yes, whenever a standing changes from winning to outbid, whatever the reason.
- client: (a) never because of a cancel. That banner is only for when someone else beats you.

### Q12 Bids placed before this change
Can bidders also cancel bids they placed before this feature goes live? Options: (a) yes, every existing active bid; (b) no, only bids placed from now on.
- client: (a) yes, though the 5 minute rule still applies to them.

### Q13 What "done" looks like
How will you know this works? Options: (a) a bidder can cancel from the "My bids" page and the price to beat updates at once for everyone; (b) the same, plus a count of cancelled bids you can check; (c) something else (please describe).
- client: (a)

## Contradictions
- R4 (brief: a cancelled bid "should just disappear from their list") against Q6 (client: "Keep it in the list marked "cancelled" with no standing ... Forget what I wrote in the brief"). Followed Q6: it is the later, more specific answer and the client withdrew the brief line. A cancelled bid stays in My bids with status `cancelled` and standing `null`, which is what the baseline `list_my_bids` already does for non-active bids, so the first baseline conflict above no longer applies.
- R5 ("as if that bid had never been placed") and Q2 (5 minute limit) do not contradict: R5 describes the effect of a cancel, Q2 limits when a cancel is allowed. Both are followed.

## BA decisions
- D1 (Q8) After a successful cancel the row stays in the list (Q6) showing status `cancelled`, and a notice line reads `Bid <id> on auction <auction_id> cancelled.`; a failed cancel shows the API error text in the existing red error line, because the bidder needs to know the cancel worked and why it did not, and the red line is already where the page shows errors.
- D2 Cancelling a bid of another user, or a bid id that does not exist, answers 404 `bid not found`, because the page only ever shows the bidder's own bids and the answer should not reveal other users' bids.
- D3 The 5 minute window is inclusive: a cancel is accepted while `now - created_at` is at most 300000 ms, measured on the server clock in epoch milliseconds, because a precise boundary is needed for tests and time zones do not apply to epoch times.
- D4 The "Cancel bid" button shows on every active row, whatever its age, and the server decides, because Q2 says a late bidder "gets a message saying it is too late to cancel", which needs the button to be there.
- D5 After any answer to a cancel request the page reloads My bids from the first page and refreshes the minimum bid hint, because one cancel can change the standing of other rows and the minimum next bid (R5, R6).
- D6 After a successful cancel the page clears the stored standing of that auction, as it does after placing a bid, so that the cancel never shows the outbid banner (Q11). A cancel can only raise other bidders' standing, so no other bidder can get the banner from it.
