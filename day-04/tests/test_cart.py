"""Run from day-04/: python -m unittest discover -s tests -t . -v"""

import unittest

from shop.cart import merge_carts


class MergeCartsTest(unittest.TestCase):
    def test_disjoint_items_are_combined(self):
        self.assertEqual(merge_carts({"a": 1}, {"b": 2}), {"a": 1, "b": 2})

    def test_same_sku_quantities_are_summed(self):
        self.assertEqual(merge_carts({"a": 2, "b": 1}, {"a": 3}), {"a": 5, "b": 1})

    def test_inputs_are_not_modified(self):
        guest, user = {"a": 1}, {"a": 2}
        merge_carts(guest, user)
        self.assertEqual(guest, {"a": 1})
        self.assertEqual(user, {"a": 2})


if __name__ == "__main__":
    unittest.main()
