from go.base.tests.utils import VumiGoDjangoTestCase

from go.billing.models import TagPool, Account, MessageCost, Transaction


class TestTagPool(VumiGoDjangoTestCase):
    def test_unicode(self):
        tp = TagPool(name=u"pool", description=u"pool of long codes")
        self.assertEqual(unicode(tp), u"pool")


class TestAccount(VumiGoDjangoTestCase):
    def setUp(self):
        super(TestAccount, self).setUp()
        self.setup_user_api()

    def test_unicode(self):
        acc = Account(
            user=self.django_user,
            account_number=self.user_api.user_account_key)
        self.assertEqual(
            unicode(acc),
            u"%s (%s)" % (
                self.user_api.user_account_key, self.django_user.email
            )
        )


class TestMessageCost(VumiGoDjangoTestCase):
    def setUp(self):
        super(TestMessageCost, self).setUp()
        self.setup_user_api()

    def mk_msg_cost(self, account=None, tag_pool=None, **kw):
        if account is None:
            account = Account(
                user=self.django_user,
                account_number=self.user_api.user_account_key)
            account.save()
        if tag_pool is None:
            tag_pool = TagPool(name=u"pool", description=u"description")
            tag_pool.save()
        return MessageCost(account=account, tag_pool=tag_pool, **kw)

    def test_unicode(self):
        mc = self.mk_msg_cost(message_direction='inbound')
        self.assertEqual(unicode(mc), u"pool (inbound)")


class TestTransaction(VumiGoDjangoTestCase):
    def test_unicode(self):
        trans = Transaction(
            account_number="1234",
            credit_amount=123)
        trans.save()
        self.assertNotEqual(trans.pk, None)
        self.assertEqual(unicode(trans), unicode(trans.pk))
