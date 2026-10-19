"""Price helpers. All prices are integer cents."""


def apply_discount(price_cents, percent):
    """Return the price after a percentage discount, rounded half up to a whole cent."""
    if isinstance(price_cents, bool) or not isinstance(price_cents, int):
        raise ValueError("price_cents must be an integer")
    if price_cents < 0:
        raise ValueError("price_cents must not be negative")
    if not 0 <= percent <= 100:
        raise ValueError("percent must be between 0 and 100")
    return (price_cents * (100 - percent) + 50) // 100
