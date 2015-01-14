from decimal import Decimal

import mock
from go.base.tests.helpers import GoDjangoTestCase, DjangoVumiApiHelper
from go.billing.templatetags.billing_tags import (
    format_cents, format_credits, credit_balance)


class TestFormatCents(GoDjangoTestCase):
    @mock.patch('go.billing.settings.DOLLAR_DECIMAL_PLACES', 3)
    def test_format_cents(self):
        self.assertEqual(format_cents(Decimal('2')), '0.020')
        self.assertEqual(format_cents(Decimal('23')), '0.230')
        self.assertEqual(format_cents(Decimal('0.1')), '0.001')
        self.assertEqual(format_cents(Decimal('0.2')), '0.002')

        self.assertEqual(
            format_cents(Decimal('123456789.9876')),
            '1,234,567.899')


class TestFormatCredits(GoDjangoTestCase):
    def test_format_credits(self):
        self.assertEqual(format_credits(Decimal('2.00')), '2.00')
        self.assertEqual(format_credits(Decimal('0.23')), '0.23')
        self.assertEqual(format_credits(Decimal('0.028')), '0.02')

        self.assertEqual(
            format_credits(Decimal('123456789.9876')),
            '123,456,789.98')


class TestCreditBalance(GoDjangoTestCase):
    def setUp(self):
        self.vumi_helper = self.add_helper(DjangoVumiApiHelper())

    def mk_user(self, balance):
        self.user_helper = self.vumi_helper.make_django_user()
        user = self.user_helper.get_django_user()
        account = user.account_set.get()
        account.credit_balance = balance
        account.save()
        return user

    def test_zero(self):
        user = self.mk_user(Decimal('0.0'))
        self.assertEqual(credit_balance(user), '0.00 credits')

    def test_singular(self):
        user = self.mk_user(Decimal('1.0'))
        self.assertEqual(credit_balance(user), '1.00 credit')

    def test_plural(self):
        user = self.mk_user(Decimal('123456789.9876'))
        self.assertEqual(credit_balance(user), '123,456,789.98 credits')
