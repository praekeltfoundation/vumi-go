from decimal import Decimal

import mock
from go.billing.templatetags.billing_tags import dollars
from go.base.tests.helpers import GoDjangoTestCase


class TestDollars(GoDjangoTestCase):
    @mock.patch('go.billing.settings.DOLLAR_FORMAT', '%.3f')
    def test_dollars(self):
        self.assertEqual(dollars(Decimal('2')), '0.020')
        self.assertEqual(dollars(Decimal('23')), '0.230')
        self.assertEqual(dollars(Decimal('0.1')), '0.001')
        self.assertEqual(dollars(Decimal('0.2')), '0.002')
