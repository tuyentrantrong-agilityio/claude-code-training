# Retro issues (draft, create these in GitLab and assign to yourself)

## 1. Standing is computed with one query per bid and no index

Problem: `list_my_bids` runs a query per bid to find the top bid of its
auction, and the table has no index on (auction_id, status, amount).
Impact: slow with many bids.
Done when: one query (or a join) computes standing for the page, an index
exists, and the existing standing tests still pass.

## 2. Outbid banner only checks the first 100 bids and shows once

Problem: the banner uses `/api/bids?limit=100`, so bids beyond 100 are never
checked, and the stored standing is overwritten on the next load.
Done when: the banner covers all of the user's bids (or a server endpoint
reports outbid auctions) and the behaviour on repeated loads is decided with BA.

## 3. JavaScript in index.html has no automated test

Problem: only markup is tested; banner and localStorage logic were checked by
hand in Chrome.
Done when: the logic lives in a small testable script or a documented manual
test script is added to day-12, and the team agrees which one.

## 4. Test review follow-ups (from day-15/qa-test-review.md)

Problem: race test can hang without a barrier timeout, it does not check the
stored winner, and the cursor test hides which case failed.
Done when: barrier timeout added, a mixed-amount race test added, subTest used
for cursors.
