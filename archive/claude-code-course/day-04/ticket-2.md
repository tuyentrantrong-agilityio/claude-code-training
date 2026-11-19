# Ticket 2: Items disappear from the cart after login

**Component:** `shop/cart.py`, `merge_carts`

## Description

A guest adds 2 of sku `a` to the cart, then logs in. The saved user cart
already has 3 of sku `a`. After login the cart shows 3, not 5. Support says the
guest quantities are silently dropped whenever the same sku exists in both
carts.

## Expected

Quantities of the same sku are summed. Skus present in only one cart are kept.

## Actual

The user cart quantity overwrites the guest cart quantity.

## Notes

- Neither input cart may be modified.
- Failing test: `tests/test_cart.py`, `test_same_sku_quantities_are_summed`.
