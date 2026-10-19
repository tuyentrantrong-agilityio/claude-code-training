# Ticket 1: apply_discount accepts invalid prices

**Component:** `day-04/shop/pricing.py`, `apply_discount`

## Description

`apply_discount` checks `percent` but not `price_cents`. A negative price such
as `apply_discount(-500, 10)` returns -450, and a float price such as
`apply_discount(9.99, 10)` returns a float. Both should be rejected before any
discount is applied.

## Expected

- `price_cents` must be an `int` and not negative; otherwise raise `ValueError`.
- `bool` values are rejected even though `bool` is a subclass of `int`.
- A price of 0 is valid and returns 0.

## Notes

- Keep the existing `percent` check and the half-up rounding.
- Add tests in `day-04/tests/test_pricing.py`; do not change the existing ones.
