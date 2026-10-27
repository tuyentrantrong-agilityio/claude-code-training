# QA test matrix

| ID | Ticket | Scenario | Input / state | Expected |
|----|--------|----------|---------------|----------|
| TC1 | T1 | Single bid is top | u42 bid 100 on a7 | winning |
| TC2 | T1 | Beaten | u42 100, u5 150 on a7 | u42 outbid |
| TC3 | T1 | Equal amount, earlier wins | u42 100 at t1, u5 100 at t2 (insert directly, bypass T3) | u42 winning |
| TC4 | T1 | Same user, two bids | u42 100 then 120 on a7 | 120 winning, 100 outbid |
| TC5 | T1 | Standing over whole auction | limit 1, top bid is on another page | standing still correct |
| TC6 | T1 | Paging unchanged | limit 2 with cursor | same order and next_cursor as before |
| TC7 | T1 | Limit rules | limit 0 and 101 | ValueError |
| TC8 | T2 | Row labels | mixed standings | Winning / Outbid text per row |
| TC9 | T2 | Load more | click Load more | new rows show standing |
| TC10 | T2 | API error | page size 0, Reload | red message, Load more hidden |
| TC11 | T3 | Below highest | highest 150, bid 100 | rejected, not stored |
| TC12 | T3 | Equal to highest | highest 150, bid 150 | rejected |
| TC13 | T3 | Just above | highest 150, bid 151 | stored |
| TC14 | T3 | First bid | no bids, bid 1 | stored |
| TC15 | T3 | Invalid input | amount -5, 0, "abc" | existing 400 messages unchanged |
| TC16 | T3 | Self outbid | u42 on top, u42 bids higher | pending Q5 |
| TC17 | T3 | Rejection response | bid 100 vs 150 | status and message pending Q7 |
| TC18 | T3 | Two equal bids at once | concurrent bids | only one stored |
| TC19 | T4 | Banner | winning then outbid, reload | banner shown |
| TC20 | T4 | No change | reload twice | no banner |
