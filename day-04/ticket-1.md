# Ticket 1: Discounted price is off by one cent on half-cent results

**Component:** `shop/pricing.py`, `apply_discount`

## Description

Customers report that some discounted prices are one cent higher than the
amount shown in the product spec. Example: a 995 cent item with a 10% coupon
should cost 896 cents (895.5 rounded half up) but the checkout charges 895.

## Expected

`apply_discount` rounds half up to a whole cent, as its docstring states.

## Actual

`apply_discount(995, 10)` returns 895.

## Notes

- Prices are integer cents. Avoid float rounding surprises.
- Keep the existing validation of `percent`.
- Failing test: `tests/test_pricing.py`, `test_half_cent_rounds_up`.
