# Intake: Minimum raise on bids

Brief: [brief.md](brief.md)

## Requirements
- R1 A new bid on an auction that already has a highest bid is accepted only if its amount beats that highest bid by at least the minimum step; otherwise it is rejected (brief: "beat the current best by a minimum step")
- R2 The minimum step is a flat 5, the same on every auction (brief: "a flat 5 on every auction")
- R3 A rejected bid tells the bidder the amount they need to offer instead (brief: "told clearly what they need to offer instead")
- R4 The first bid on an auction may still be any amount allowed today (1 or more) (brief: "The first bid on an auction should stay free")

## Assumptions
- A1 "Beat by 5" means a bid of exactly highest + 5 is accepted (highest 100 -> 105 is enough, 104 is not): confirm in Q1
- A2 The message for a too-low bid names the exact smallest amount that would be accepted, on the page and in the API: confirm in Q2
- A3 The step also applies when a bidder raises their own winning bid: confirm in Q3
- A4 The step is measured from the highest active bid only; cancelled bids are ignored, and an auction whose bids are all cancelled takes a free first bid again: confirm in Q4
- A5 Bids placed before the change stay as they are, with their current standing, even if they beat the previous bid by less than 5: confirm in Q5
- A6 The page does not show the minimum next bid before the bidder tries; they only learn it from the error: confirm in Q6
- A7 Of two bids sent at the same moment, the second one is checked against the first one once stored (highest 100, bids 105 and 108 at once: 105 is stored first, 108 is then rejected because it needs 110): confirm in Q7
- A8 Amounts are whole euros and the step of 5 means 5 euros: confirm in Q8
- A9 The step is fixed at 5; nobody can change it per auction or from the page: confirm in Q9
- A10 After a rejected bid the amount the bidder typed stays in the form: confirm in Q10
- A11 Done means the rule is enforced for every bid placed through the website and its API: confirm in Q11

## Conflicts with the baseline
- Placing a bid: the baseline accepts any amount greater than the highest active amount (highest + 1). The brief requires highest + 5 (subject to Q1).
- Rejection message: the baseline returns 409 `bid must be higher than <highest>`, which names the current highest, not what to offer. The brief asks for the amount to offer instead (Q2).
- The baseline lists "minimum increment" under "Not in the baseline"; this feature adds it.
- The brief's goal "make auctions end at higher prices" refers to auction end, which does not exist in the baseline (no end time, no winner). Treated as the motivation, not a requirement (Q11).

## Open questions
### Q1 Exactly 5 more
If the best bid on an auction is 100, is a bid of 105 accepted?
- a) Yes, 105 or more is accepted, 104 is rejected
- b) No, it must be more than 105 (106 or more)
- client: a, exactly the best bid plus the step is fine. The step depends on the best bid already there, not on what the bidder offers.

### Q2 What the bidder is told
When a bid is too low, what should the bidder read? For example, with a best bid of 100 and an offer of 102:
- a) "Your bid must be at least 105"
- b) "Bid at least 105 (current highest 100, minimum step 5)"
- c) Other wording you give us
- client: c, something like "bid must be at least 60", it just has to name the lowest amount allowed. Same message from the website's API too, with the same 409 error as today.

### Q3 Raising your own bid
If you already hold the best bid of 100 on an auction and want to raise it, must you also add at least 5?
- a) Yes, same rule for everyone
- b) No, your own raise can be any higher amount
- c) No, you cannot raise your own winning bid at all
- client: a, same rule for everyone.

### Q4 Cancelled bids
Bids can be cancelled. Should the minimum be counted from the best bid that still counts (ignoring cancelled ones)? And if every bid on an auction has been cancelled, is the next bid free again like a first bid?
- a) Yes to both
- b) Count from the best still-counting bid, but once an auction has had any bid, the next one is never free
- c) Something else
- client: a, yes to both.

### Q5 Bids placed before the change
Existing auctions may already have bids that beat the previous one by only 1 euro. What should happen to them?
- a) Leave them as they are; the rule only applies to new bids
- b) Something else (please describe)
- client: a, leave old bids alone.

### Q6 Showing the minimum up front
Should the page show the minimum next bid before the bidder tries?
- a) No, only tell them after a too-low bid
- b) Yes, show "Minimum next bid: 105" next to each auction in My bids
- c) Yes, show it in the bid form once an auction number is typed
- client: c, in the bid form for the auction number the bidder typed. Wording and colour, and what it shows for an auction with no bids yet: you decide.

### Q7 Two bids at the same moment
Best bid 100. Two bidders offer 105 and 108 at the very same moment. What should happen?
- a) Whichever arrives first is kept; the other is then checked against it (so 108 after 105 is rejected, it would need 110)
- b) Both are checked against 100, so both can be kept
- c) You decide
- client: not sure, whatever works for the team.

### Q8 Whole euros
Are all bids in whole euros, with the step being 5 euros?
- a) Yes, whole euros only
- b) No, amounts can have cents (please say how the step works then)
- client: a, whole euros only.

### Q9 Changing the step
Is 5 fixed for now, or should someone be able to change it?
- a) Fixed at 5 for every auction
- b) Changeable later, the same for all auctions
- c) Different per auction
- client: a, fixed and the same everywhere, but not a flat 5, I was wrong there. The step is 10 when the best bid is under 1000, and 50 when it is 1000 or more.

### Q10 After a too-low bid
After a rejected bid, what happens to the amount the bidder typed in the form?
- a) It stays as typed, so they can edit it
- b) It is replaced by the minimum amount they need to offer
- c) The form is cleared
- client: a, it stays as typed.

### Q11 What counts as done
What do you need to see to call this finished?
- a) Too-low bids are refused on the website with the clear message, and normal bids still work
- b) a) plus some proof that final prices went up (reporting)
- c) Something else
- client: a, no reporting needed.

## Contradictions
- Brief "a flat 5 on every auction" (R2) vs Q9 "step is 10 when the best bid is under 1000, and 50 when it is 1000 or more". Followed Q9: it is the later, more specific answer and the client says "I was wrong there". R2 is replaced by this two-tier step; the 5 in Q1 and Q7 examples is read with the new step (highest 100 -> 110 accepted, 109 rejected).
- Q1 says "exactly the best bid plus the step is fine" and that the step depends on the best bid already there. Followed it together with Q9: the tier is chosen by the current highest amount, not by the offered amount (highest 999 -> minimum 1009; highest 1000 -> minimum 1050).

## BA decisions
- D1 Two bids at the same moment (Q7): they are checked one after the other; the first stored becomes the highest and the second must beat it by the step, so of two bids of 110 on a highest of 100 exactly one is stored and the other gets 409 "bid must be at least 120", because the baseline already checks and inserts in one statement and this keeps one simple rule for everyone.
- D2 Hint wording and look (Q6): the bid form shows "Minimum next bid: 110" on its own line under the Amount field, in grey normal-size text (not the red error colour), because it is help, not an error.
- D3 Hint for an auction with no active bids (Q6): "No bids yet: any amount from 1", because the first bid is free (R4, Q4).
- D4 Hint when the Auction ID field is empty or not a whole number of 1 or more: no hint text and no request, because there is no auction to look up.
- D5 Hint refresh: on every change of the Auction ID field and after every bid attempt (accepted or rejected); no timed polling, because the server check is authoritative and the 409 message always names the current minimum.
- D6 The hint reads a new endpoint `GET /api/auctions/<auction_id>/minimum-bid`, because the page cannot work out the highest bid of an auction from My bids alone (other users' bids are not listed).
- D7 If the highest bid plus the step would exceed 9223372036854775807 (2^63-1), every new bid on that auction gets 409 naming that larger number, because no allowed amount can beat it and the message must still name the lowest amount.
