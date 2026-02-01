from django.test import SimpleTestCase
from decimal import Decimal

from .utils.money import to_onepipe_amount


class MoneyUtilsTests(SimpleTestCase):
    def test_to_onepipe_amount_integer_input(self):
        self.assertEqual(to_onepipe_amount(Decimal('100000')), '100000000')
        self.assertEqual(to_onepipe_amount('100000'), '100000000')
        self.assertEqual(to_onepipe_amount(100000), '100000000')

    def test_to_onepipe_amount_fractional(self):
        # 100.25 * 1000 => 100250
        self.assertEqual(to_onepipe_amount(Decimal('100.25')), '100250')
        # small fractional values
        self.assertEqual(to_onepipe_amount('0.001'), '1')
