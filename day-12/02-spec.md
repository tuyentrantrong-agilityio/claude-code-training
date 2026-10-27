# Spec: bid standing in My Bids

## Context

`day-02/auction/bids.py` stores bids (id, user_id, auction_id, amount, status,
created_at). `GET /api/bids` (day-11 webapp) lists the current user's bids.
Today a bid has no information about other bidders' standing.

## Definitions

- Highest bid of an auction: max amount; on equal amount the lowest created_at,
  then the lowest id.
- Standing: `winning` if the bid is the highest bid of its auction, else `outbid`.

## Behaviour

1. Each item from the bids list carries a `standing` field (`winning` or `outbid`).
2. The web table shows the standing per row.
3. Placing a bid is rejected unless amount is greater than the current highest
   amount of that auction (any user). First bid on an auction: any amount >= 1.
4. Existing rules unchanged: limit 1..100, cursor pagination on (created_at, id).

## Not in scope

Email or push, minimum increment, auction end time, multiple users in the web
UI (the webapp has one fixed user, 42).
