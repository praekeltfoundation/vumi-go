from decimal import Decimal, Context, Inexact, Rounded

from go.vumitools.tests.helpers import djangotest_imports

with djangotest_imports(globals()):
    from go.base.tests.helpers import GoDjangoTestCase, DjangoVumiApiHelper
    from go.billing.models import (
        TagPool, Account, MessageCost, Transaction, create_billing_account,
        LowCreditNotification)
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
        self.assertEqual(acc.credit_balance, Decimal('0.0'))
        self.assertEqual(acc.last_topup_balance, Decimal('0.0'))

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
                Decimal('1.0'), Decimal('50.0')),
            Decimal('15.0'))

    def test_apply_markup_and_convert_to_credits_with_context(self):
        context = Context()
        self.assertEqual(
            MessageCost.apply_markup_and_convert_to_credits(
                Decimal('1.0'), QUANTIZATION_EXPONENT,
                context=context),
            Decimal('10.0'))
        self.assertEqual(context.flags[Inexact], 1)
        self.assertEqual(context.flags[Rounded], 1)

    def test_calculate_message_credit_cost(self):
        self.assertEqual(
            MessageCost.calculate_message_credit_cost(
                Decimal('1.0'), Decimal('50.0')),
            Decimal('15.0'))

    def test_calculate_message_credit_cost_with_context(self):
        context = Context()
        self.assertEqual(
            MessageCost.calculate_message_credit_cost(
                Decimal('1.0'), QUANTIZATION_EXPONENT,
                context=context),
            Decimal('10.0'))
        self.assertEqual(context.flags[Inexact], 1)
        self.assertEqual(context.flags[Rounded], 1)

    def test_calculate_storage_credit_cost(self):
        self.assertEqual(
            MessageCost.calculate_storage_credit_cost(
                Decimal('1.0'), Decimal('50.0')),
            Decimal('15.0'))

    def test_calculate_storage_credit_cost_with_context(self):
        context = Context()
        self.assertEqual(
            MessageCost.calculate_storage_credit_cost(
                Decimal('1.0'), QUANTIZATION_EXPONENT,
                context=context),
            Decimal('10.0'))
        self.assertEqual(context.flags[Inexact], 1)
        self.assertEqual(context.flags[Rounded], 1)

    def test_calculate_session_credit_cost(self):
        self.assertEqual(
            MessageCost.calculate_session_credit_cost(
                Decimal('1.0'), Decimal('50.0')),
            Decimal('15.0'))

    def test_calculate_session_credit_cost_with_context(self):
        context = Context()
        self.assertEqual(
            MessageCost.calculate_session_credit_cost(
                Decimal('1.0'), QUANTIZATION_EXPONENT,
                context=context),
            Decimal('10.0'))
        self.assertEqual(context.flags[Inexact], 1)
        self.assertEqual(context.flags[Rounded], 1)

    def test_calculate_session_length_cost(self):
        self.assertEqual(
            MessageCost.calculate_session_length_cost(
                unit_cost=Decimal('2.0'),
                unit_length=Decimal('20.0'),
                length=Decimal('23.0')),
            Decimal('4.0'))

    def test_calculate_session_length_cost_zero_unit_length(self):
        self.assertEqual(
            MessageCost.calculate_session_length_cost(
                unit_cost=Decimal('2.0'),
                unit_length=Decimal(0),
                length=Decimal('23.0')),
            Decimal(0))

    def test_calculate_session_length_cost_none_unit_cost(self):
        self.assertEqual(
            MessageCost.calculate_session_length_cost(
                unit_cost=None,
                unit_length=Decimal('20.0'),
                length=Decimal('23.0')),
            Decimal(0))

    def test_calculate_session_length_cost_none_unit_length(self):
        self.assertEqual(
            MessageCost.calculate_session_length_cost(
                unit_cost=Decimal('2.0'),
                unit_length=None,
                length=Decimal('23.0')),
            Decimal(0))

    def test_calculate_session_length_cost_none_length(self):
        self.assertEqual(
            MessageCost.calculate_session_length_cost(
                unit_cost=Decimal('2.0'),
                unit_length=Decimal('20.0'),
                length=None),
            Decimal(0))

    def test_calculate_credit_cost(self):
        self.assertEqual(
            MessageCost.calculate_credit_cost(
                message_cost=Decimal('1.0'),
                storage_cost=Decimal('3.0'),
                session_cost=Decimal('2.0'),
                markup_percent=Decimal('10.0'),
                session_created=False),
            Decimal('44.0'))

        self.assertEqual(
            MessageCost.calculate_credit_cost(
                message_cost=Decimal('5.0'),
                storage_cost=Decimal('3.0'),
                session_cost=Decimal('2.0'),
                markup_percent=Decimal('10.0'),
                session_created=False),
            Decimal('88.0'))

    def test_calculate_credit_cost_for_new_session(self):
        self.assertEqual(
            MessageCost.calculate_credit_cost(
                message_cost=Decimal('1.0'),
                storage_cost=Decimal('3.0'),
                session_cost=Decimal('2.0'),
                markup_percent=Decimal('10.0'),
                session_created=True),
            Decimal('66.0'))

        self.assertEqual(
            MessageCost.calculate_credit_cost(
                message_cost=Decimal('5.0'),
                storage_cost=Decimal('3.0'),
                session_cost=Decimal('2.0'),
                markup_percent=Decimal('20.0'),
                session_created=True),
            Decimal('120.0'))

    def test_calculate_credit_cost_with_context(self):
        context = Context()

        self.assertEqual(
            MessageCost.calculate_credit_cost(
                message_cost=Decimal('1.0'),
                storage_cost=Decimal('1.0'),
                markup_percent=QUANTIZATION_EXPONENT,
                session_cost=Decimal('2.0'),
                session_created=True,
                context=context),
            Decimal('40.0'))

        self.assertEqual(context.flags[Inexact], 1)
        self.assertEqual(context.flags[Rounded], 1)

    def test_calculate_credit_cost_with_session_length(self):
        self.assertEqual(
            MessageCost.calculate_credit_cost(
                message_cost=Decimal('1.0'),
                storage_cost=Decimal('3.0'),
                session_cost=Decimal('2.0'),
                session_unit_cost=Decimal('2.0'),
                markup_percent=Decimal('10.0'),
                session_created=True,
                session_length=Decimal('25.0'),
                session_unit_length=Decimal('20.0')),
            Decimal('110.0'))

    def test_message_credit_cost(self):
        mc = self.mk_msg_cost(
            message_cost=Decimal('5.0'),
            storage_cost=Decimal('3.0'),
            markup_percent=Decimal('50.0'),
            session_cost=Decimal('100.0'))
        self.assertEqual(mc.message_credit_cost, Decimal('75.0'))

    def test_session_credit_cost(self):
        mc = self.mk_msg_cost(
            message_cost=Decimal('100.0'),
            storage_cost=Decimal('3.0'),
            markup_percent=Decimal('50.0'),
            session_cost=Decimal('6.0'))
        self.assertEqual(mc.session_credit_cost, Decimal('90.0'))

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


class TestLowCreditNotification(GoDjangoTestCase):
    def setUp(self):
        self.vumi_helper = self.add_helper(DjangoVumiApiHelper())
        # Django overides these settings before tests start, so set them here
        self.vumi_helper.patch_settings(
            EMAIL_BACKEND='djcelery_email.backends.CeleryEmailBackend',
            CELERY_EMAIL_BACKEND='django.core.mail.backends.locmem.'
                                 + 'EmailBackend')
        self.user_helper = self.vumi_helper.make_django_user()

    def mk_notification(self, percent, balance):
        self.django_user = self.user_helper.get_django_user()
        self.acc = Account.objects.get(user=self.django_user)
        notification = LowCreditNotification(
            account=self.acc, threshold=Decimal(percent),
            credit_balance=Decimal(balance))
        notification.save()
        return notification

    def test_unicode(self):
        notification = self.mk_notification('0.5', '314.1')
        self.assertEqual(
            unicode(notification),
            u'50.0%% threshold for %s' % self.acc)

    def test_fields(self):
        notification = self.mk_notification('0.55', '27.17')
        self.assertEqual(notification.account, self.acc)
        self.assertEqual(notification.credit_balance, Decimal('27.17'))
        self.assertEqual(notification.threshold, Decimal('0.55'))
