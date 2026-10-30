"""Cart helpers. A cart is a dict mapping sku (str) to quantity (int)."""


def merge_carts(guest_cart, user_cart):
    """Merge a guest cart into a user cart after login and return a new cart."""
    merged = dict(user_cart)
    for sku, qty in guest_cart.items():
        merged[sku] = merged.get(sku, 0) + qty
    return merged
