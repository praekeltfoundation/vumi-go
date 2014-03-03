import decimal

from go.base.tests.helpers import GoDjangoTestCase, DjangoVumiApiHelper
from go.billing.models import (
    TagPool, Account, MessageCost, Transaction, create_billing_account)
from go.billing.settings import QUANTIZATION_EXPONENT


class TestTagPool(GoDjangoTestCase):
    def test_unicode(self):
        tp = TagPool(name=u"pool", description=u"pool of long codes")
        self.assertEqual(unicode(tp), u"pool")


class TestAccount(GoDjangoTestCase):
    def setUp(self):
        self.vumi_helper = self.add_helper(DjangoVumiApiHelper())
        self.user_helper = self.vumi_helper.make_django_user()

    def test_unicode(self):
        django_user = self.user_helper.get_django_user()
        acc = Account.objects.get(user=django_user)
        self.assertEqual(
            unicode(acc),
            u"%s (%s)" % (self.user_helper.account_key, django_user)
        )

    def test_post_save_hook_created(self):
        user_helper = self.vumi_helper.make_django_user(
            email="newuser@example.com")
        django_user = user_helper.get_django_user()
        profile = django_user.get_profile()
        acc = Account.objects.get(user=django_user)
        self.assertEqual(acc.user, django_user)
        self.assertEqual(acc.account_number, profile.user_account)
        self.assertEqual(acc.credit_balance, decimal.Decimal('0.0'))
        self.assertEqual(acc.alert_threshold, decimal.Decimal('0.0'))
        self.assertEqual(acc.alert_credit_balance, decimal.Decimal('0.0'))

    def test_post_save_hook_not_created(self):
        django_user = self.user_helper.get_django_user()
        account = Account.objects.get(user=django_user)
        account.delete()
        profile = django_user.get_profile()
        create_billing_account(profile.__class__, profile, created=False)
        self.assertEqual(
            list(Account.objects.filter(user=django_user).all()), [])


class TestMessageCost(GoDjangoTestCase):
    def setUp(self):
        self.vumi_helper = self.add_helper(DjangoVumiApiHelper())
        self.user_helper = self.vumi_helper.make_django_user()

    def mk_msg_cost(self, account=None, tag_pool=None, **kw):
        if account is None:
            account = Account.objects.get(
                user=self.user_helper.get_django_user())
        if tag_pool is None:
            tag_pool = TagPool(name=u"pool", description=u"description")
            tag_pool.save()
        return MessageCost(account=account, tag_pool=tag_pool, **kw)

    def test_apply_markup_and_convert_to_credits(self):
        self.assertEqual(
            MessageCost.apply_markup_and_convert_to_credits(
                decimal.Decimal('1.0'), decimal.Decimal('50.0')),
            decimal.Decimal('15.0'))

    def test_apply_markup_and_convert_to_credits_with_context(self):
        context = decimal.Context()
        self.assertEqual(
            MessageCost.apply_markup_and_convert_to_credits(
                decimal.Decimal('1.0'), QUANTIZATION_EXPONENT,
                context=context),
            decimal.Decimal('10.0'))
        self.assertEqual(context.flags[decimal.Inexact], 1)
        self.assertEqual(context.flags[decimal.Rounded], 1)

    def test_calculate_message_credit_cost(self):
        self.assertEqual(
            MessageCost.calculate_message_credit_cost(
                decimal.Decimal('1.0'), decimal.Decimal('50.0')),
            decimal.Decimal('15.0'))

    def test_calculate_message_credit_cost_with_context(self):
        context = decimal.Context()
        self.assertEqual(
            MessageCost.calculate_message_credit_cost(
                decimal.Decimal('1.0'), QUANTIZATION_EXPONENT,
                context=context),
            decimal.Decimal('10.0'))
        self.assertEqual(context.flags[decimal.Inexact], 1)
        self.assertEqual(context.flags[decimal.Rounded], 1)

    def test_calculate_session_credit_cost(self):
        self.assertEqual(
            MessageCost.calculate_session_credit_cost(
                decimal.Decimal('1.0'), decimal.Decimal('50.0')),
            decimal.Decimal('15.0'))

    def test_calculate_session_credit_cost_with_context(self):
        context = decimal.Context()
        self.assertEqual(
            MessageCost.calculate_session_credit_cost(
                decimal.Decimal('1.0'), QUANTIZATION_EXPONENT,
                context=context),
            decimal.Decimal('10.0'))
        self.assertEqual(context.flags[decimal.Inexact], 1)
        self.assertEqual(context.flags[decimal.Rounded], 1)

    def test_calculate_credit_cost(self):
        self.assertEqual(
            MessageCost.calculate_credit_cost(
                decimal.Decimal('1.0'), decimal.Decimal('10.0'),
                decimal.Decimal('2.0'), session_created=False),
            decimal.Decimal('11.0'))
        self.assertEqual(
            MessageCost.calculate_credit_cost(
                decimal.Decimal('5.0'), decimal.Decimal('20.0'),
                decimal.Decimal('2.0'), session_created=False),
            decimal.Decimal('60.0'))

    def test_calculate_credit_cost_for_new_session(self):
        self.assertEqual(
            MessageCost.calculate_credit_cost(
                decimal.Decimal('1.0'), decimal.Decimal('10.0'),
                decimal.Decimal('2.0'), session_created=True),
            decimal.Decimal('33.0'))
        self.assertEqual(
            MessageCost.calculate_credit_cost(
                decimal.Decimal('5.0'), decimal.Decimal('20.0'),
                decimal.Decimal('2.0'), session_created=True),
            decimal.Decimal('84.0'))

    def test_calculate_credit_cost_with_context(self):
        context = decimal.Context()
        self.assertEqual(
            MessageCost.calculate_credit_cost(
                decimal.Decimal('1.0'), QUANTIZATION_EXPONENT,
                decimal.Decimal('2.0'), session_created=True,
                context=context),
            decimal.Decimal('30.0'))
        self.assertEqual(context.flags[decimal.Inexact], 1)
        self.assertEqual(context.flags[decimal.Rounded], 1)

    def test_message_credit_cost(self):
        mc = self.mk_msg_cost(
            message_cost=decimal.Decimal('5.0'),
            markup_percent=decimal.Decimal('50.0'),
            session_cost=decimal.Decimal('100.0'))
        self.assertEqual(mc.message_credit_cost, decimal.Decimal('75.0'))

    def test_session_credit_cost(self):
        mc = self.mk_msg_cost(
            message_cost=decimal.Decimal('100.0'),
            markup_percent=decimal.Decimal('50.0'),
            session_cost=decimal.Decimal('6.0'))
        self.assertEqual(mc.session_credit_cost, decimal.Decimal('90.0'))

    def test_unicode(self):
        mc = self.mk_msg_cost(message_direction='inbound')
        self.assertEqual(unicode(mc), u"pool (inbound)")


class TestTransaction(GoDjangoTestCase):
    def test_unicode(self):
        trans = Transaction(
            account_number="1234",
            credit_amount=123)
        trans.save()
        self.assertNotEqual(trans.pk, None)
        self.assertEqual(unicode(trans), unicode(trans.pk))
