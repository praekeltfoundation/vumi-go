import decimal

from go.base.tests.helpers import GoDjangoTestCase, DjangoVumiApiHelper
from go.billing.models import TagPool, Account, MessageCost, Transaction


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
        acc = Account(
            user=django_user, account_number=self.user_helper.account_key)
        self.assertEqual(
            unicode(acc),
            u"%s (%s)" % (self.user_helper.account_key, django_user)
        )


class TestMessageCost(GoDjangoTestCase):
    def setUp(self):
        self.vumi_helper = self.add_helper(DjangoVumiApiHelper())
        self.user_helper = self.vumi_helper.make_django_user()

    def mk_msg_cost(self, account=None, tag_pool=None, **kw):
        if account is None:
            account = Account(
                user=self.user_helper.get_django_user(),
                account_number=self.user_helper.account_key)
            account.save()
        if tag_pool is None:
            tag_pool = TagPool(name=u"pool", description=u"description")
            tag_pool.save()
        return MessageCost(account=account, tag_pool=tag_pool, **kw)

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

    def test_credit_cost(self):
        mc = self.mk_msg_cost(
            message_cost=decimal.Decimal('5.0'),
            markup_percent=decimal.Decimal('50.0'),
            session_cost=decimal.Decimal('100.0'))
        self.assertEqual(mc.credit_cost, decimal.Decimal('75.0'))

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
