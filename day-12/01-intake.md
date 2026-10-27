# BA intake

## Requirements extracted

| ID | Requirement | Source phrase |
|----|-------------|---------------|
| R1 | Each bid in My Bids shows whether it is currently the highest bid on its auction | "see right away if they are on top" |
| R2 | A bid that was beaten is shown as outbid | "somebody beats them" |
| R3 | Optional hint to the user when they are outbid | "maybe get a hint" |
| R4 | Reject bids that are not sensible | "don't let people bid something silly" |

## Open questions sent back to the client

| # | Question | Status |
|---|----------|--------|
| Q1 | "On top" means highest amount. Tie on amount: does the earlier bid win? | answered: yes, earliest wins |
| Q2 | R3 hint: in-page banner, email, or push? | answered: in-page only, no email |
| Q3 | "Silly" bid: what exactly is rejected? | answered: amount must be higher than the current highest bid on that auction |
| Q4 | Is there a minimum increment? | answered: no, any amount above the highest |
| Q5 | Can a user outbid themselves? | open |
| Q6 | Does the status column ('active') matter, e.g. cancelled bids? | open |
| Q7 | Rejection message wording and HTTP status? | open |

Q5-Q7 are open on purpose: devs ask through the tickets.

## Scope

In: R1, R2, R4 (tickets T1-T3). R3 is ticket T4 (optional).
