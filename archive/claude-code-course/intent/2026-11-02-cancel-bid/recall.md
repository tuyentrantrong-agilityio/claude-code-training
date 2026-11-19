# Recall

| H | Requirement | Hidden | Covered by | Verdict |
|---|---|---|---|---|
| H1 | A bidder sees a Cancel button on each of their own active bids in My bids | no | T-01 S2 | covered |
| H2 | A cancelled bid stays in the list with status cancelled and an empty standing | no | T-01 S1, S2; T-04 S1 | covered |
| H3 | A bidder can cancel only their own bids; another user's bid is refused | no | T-01 S4 | covered |
| H4 | After a cancel, the highest bid and minimum next bid are recalculated from the remaining active bids | no | T-03 S1, S2, S5, S6 | covered |
| H5 | The bidder must confirm before the cancel happens | no | T-01 S2, S3 | covered |
| H6 | Cancelling an already cancelled bid gives a clear error and changes nothing | no | T-01 S5 | covered |
| H7 | A bid can be cancelled only within 5 minutes of being placed; later the error says it is too late | yes | T-02 S1, S2, S3 | covered |
| H8 | Cancelling a bid never triggers the outbid banner for the bidder | yes | T-04 S3, S4 | covered |
| H9 | Any active bid can be cancelled, winning or outbid | added | T-03 S1, S2 | covered |
| H10 | No limit on the number of cancels | added | T-02 S6 | covered |
| H11 | Nothing special for the owner of a bid that becomes winning again | added | T-03 S3 and its Out of scope | covered |
| H12 | After a cancel the bidder may bid again like any other bid | added | T-03 S4 | covered |
| H13 | No reason asked; no edit of amounts (cancel and bid again) | added | T-01 Out of scope | covered |
| H14 | Bids placed before the feature can be cancelled, the 5 minute rule still applies | added | T-02 S4 | covered |
| H15 | Done means: cancel from My bids and the price to beat updates for everyone | added | T-03 S1 (server answer), T-04 S1, S2 (the cancelling bidder's page) | partial |

Notes on the verdicts:

- H15 is partial: the recalculated price is right at once for every API caller (T-03 S1),
  and the page of the bidder who cancelled refreshes (T-04 S2). No ticket says what another
  bidder's already open page does; it changes only on that page's own reload or next bid.
- H3 asks that the attempt is "refused"; the tickets answer 404 `bid not found`, a client
  "you decide" item (BA decision D2), so it counts as covered.
- The planned contradiction (brief: "disappear", later answer: "keep, marked cancelled")
  was flagged by the BA in `intake.md` and followed as H2.
