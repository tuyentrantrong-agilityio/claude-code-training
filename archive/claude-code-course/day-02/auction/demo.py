"""Reproduce the pagination bug: python -m auction.demo (run from day-02/)."""
from auction.bids import connect, list_my_bids, place_bid

USER = 42
T = 1_760_000_000_000  # epoch ms


def main():
    conn = connect()
    place_bid(conn, USER, auction_id=1, amount=100, created_at=T)
    # Three bids land in the same millisecond (e.g. auto-bid fan-out).
    for auction_id in (2, 3, 4):
        place_bid(conn, USER, auction_id=auction_id, amount=200, created_at=T + 5)
    place_bid(conn, USER, auction_id=5, amount=300, created_at=T + 10)

    seen, cursor, page = [], None, 1
    while True:
        resp = list_my_bids(conn, USER, limit=2, cursor=cursor)
        ids = [b["id"] for b in resp["items"]]
        print(f"page {page}: ids={ids} next_cursor={resp['next_cursor']}")
        seen += ids
        cursor, page = resp["next_cursor"], page + 1
        if cursor is None:
            break

    all_ids = [r["id"] for r in conn.execute("SELECT id FROM bids WHERE user_id = ?", (USER,))]
    missing = sorted(set(all_ids) - set(seen))
    print(f"total in DB: {len(all_ids)}, returned: {len(seen)}, missing ids: {missing}")


if __name__ == "__main__":
    main()
