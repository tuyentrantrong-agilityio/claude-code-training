"""Run from day-04/: python -m unittest discover -s tests -t . -v"""

import unittest

from shop.pricing import apply_discount


class ApplyDiscountTest(unittest.TestCase):
    def test_whole_cent_result(self):
        self.assertEqual(apply_discount(1000, 10), 900)

    def test_no_discount(self):
        self.assertEqual(apply_discount(1000, 0), 1000)

    def test_full_discount(self):
        self.assertEqual(apply_discount(1000, 100), 0)

    def test_half_cent_rounds_up(self):
        self.assertEqual(apply_discount(995, 10), 896)

    def test_invalid_percent(self):
        with self.assertRaises(ValueError):
            apply_discount(1000, 101)

    def test_negative_price_is_rejected(self):
        with self.assertRaises(ValueError):
            apply_discount(-500, 10)

    def test_non_integer_price_is_rejected(self):
        for price in (9.99, "1000"):
            with self.subTest(price=price):
                with self.assertRaises(ValueError):
                    apply_discount(price, 10)

    def test_zero_price(self):
        self.assertEqual(apply_discount(0, 10), 0)


if __name__ == "__main__":
    unittest.main()
