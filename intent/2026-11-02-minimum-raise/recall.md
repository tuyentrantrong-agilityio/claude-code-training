# Recall

Client truth: [client-truth.md](client-truth.md). Verdicts are the orchestrator's
judgement at the reveal; the user has the final say.

| H | Requirement | Hidden | Covered by | Verdict |
|---|---|---|---|---|
| H1 | A bid on an auction with an active bid must be at least highest + minimum raise | no | T-01 S1, S2 | covered |
| H2 | The first bid on an auction may be any amount of 1 or more | no | T-01 S5; T-02 S3 | covered |
| H3 | Minimum raise is 10 under 1000 and 50 from 1000 | no | T-01 S3, S4; spec table | covered |
| H4 | A rejected bid names the lowest allowed amount | no | T-01 S2, S3, S4 | covered |
| H5 | The bid form shows the lowest allowed amount for the typed auction | no | T-03 S1-S6 | covered |
| H6 | The web API rejects a too-small bid with the same 409 and message | no | T-01 S2 | covered |
| H7 | A bid of exactly highest + minimum raise is accepted | yes | T-01 S1, S3, S4 | covered |
| H8 | The step is decided by the current highest, not the offered amount | yes | T-01 S3 (H 999 -> 1009); spec "tier is chosen by H" | covered |
| H9 | Raising your own winning bid follows the same rule | added | T-02 S1 | covered |
| H10 | Cancelled bids are ignored; all cancelled means the next bid is free | added | T-02 S2, S3 | covered |
| H11 | Old bids stay as they are | added | T-02 S4 | covered |
| H12 | Whole euros only | added | T-01 S6 (110.5 refused) | covered |
| H13 | Typed amount stays in the form after a rejection | added | T-01 S2; T-03 S5 | covered |
| H14 | Done = website and API enforce the rule; no reporting | added | T-01 S2; spec Out of scope (Q11) | covered |

## Contradiction

- Brief: flat raise of 5. Answer: 10 below 1000, 50 from 1000 (tiered).
  Flagged by the BA in `intake.md` (Contradictions) and resolved in the spec with the tiers.

## Notes for the build

- T-01 S1 keeps today's form behaviour after an accepted bid, while T-03 S6 says the
  fields keep their values after a 201. Align these when T-03 is built (T-03 is the later
  ticket and states the final behaviour).
