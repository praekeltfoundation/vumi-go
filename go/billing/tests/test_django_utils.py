""" Test for go.billing.django_utils. """

import json
from decimal import Decimal

from go.vumitools.tests.helpers import djangotest_imports

with djangotest_imports(globals()):
    from go.base.tests.helpers import GoDjangoTestCase, DjangoVumiApiHelper
    from go.billing.models import Account, Transaction
    from go.billing.tests.helpers import (
        mk_transaction, get_message_credits, get_storage_credits,
        get_session_credits, get_session_length_credits)
    from go.billing.django_utils import (
        TransactionSerializer, chunked_query, load_account_credits,
        summarize)


class TestTransactionSerializer(GoDjangoTestCase):
    def setUp(self):
        self.vumi_helper = self.add_helper(DjangoVumiApiHelper())
        self.user_helper = self.vumi_helper.make_django_user()
        self.account = Account.objects.get(
            user=self.user_helper.get_django_user())

    def test_to_json(self):
        serializer = TransactionSerializer()
        transaction = mk_transaction(self.account)
        [datum] = serializer.to_json([transaction])
        self.assertEqual(json.loads(datum), {
            u"pk": transaction.pk,
            u"model": u"billing.transaction",
            u"fields": {
                u"account_number": self.account.account_number,
                u"created": unicode(transaction.created.isoformat()),
                u"last_modified": unicode(
                    transaction.last_modified.isoformat()),
                u"provider": None,
                u"transaction_type": u"Message",
                u"credit_amount": 28.0,
                u"credit_factor": 0.25,
                u"markup_percent": 10.0,
                u"message_cost": 100.0,
                u"storage_cost": 50.0,
                u"session_cost": 10.0,
                u'session_unit_cost': 10.0,
                u'session_unit_time': 20.0,
                u'session_length_cost': 10.0,
                u'session_length_credits':
                    float(get_session_length_credits(10, 10)),
                u"message_credits": float(get_message_credits(100.0, 10.0)),
                u"storage_credits": float(get_storage_credits(50.0, 10.0)),
                u"session_credits": float(get_session_credits(10.0, 10.0)),
                u"message_direction": u"Inbound",
                u"message_id": None,
                u"session_length": 20.0,
                u"session_created": None,
                u"status": u"Completed",
                u"tag_pool_name": u"pool1",
                u"tag_name": u"tag1",
            },
        })


class TestChunkedQuery(GoDjangoTestCase):
    def setUp(self):
        self.vumi_helper = self.add_helper(DjangoVumiApiHelper())
        self.user_helper = self.vumi_helper.make_django_user()
        self.account = Account.objects.get(
            user=self.user_helper.get_django_user())

    def test_simple_query_without_remainder(self):
        query = Transaction.objects.order_by('pk').all()
        transactions = [
            mk_transaction(self.account) for _ in range(6)]
        transactions.sort(key=lambda t: t.pk)
        it = chunked_query(query, 3)
        self.assertEqual(next(it), transactions[0:3])
        self.assertEqual(next(it), transactions[3:6])
        self.assertRaises(StopIteration, next, it)

    def test_simple_query_with_remainder(self):
        query = Transaction.objects.order_by('pk').all()
        transactions = [
            mk_transaction(self.account) for _ in range(8)]
        transactions.sort(key=lambda t: t.pk)
        it = chunked_query(query, 3)
        self.assertEqual(next(it), transactions[0:3])
        self.assertEqual(next(it), transactions[3:6])
        self.assertEqual(next(it), transactions[6:8])
        self.assertRaises(StopIteration, next, it)


class TestLoadAccountCredits(GoDjangoTestCase):
    def setUp(self):
        self.vumi_helper = self.add_helper(DjangoVumiApiHelper())
        self.user_helper = self.vumi_helper.make_django_user()
        self.account = Account.objects.get(
            user=self.user_helper.get_django_user())

    def test_load_account_credits(self):
        self.account.last_topup_balance = Decimal('20.0')
        self.account.save()

        self.assertEqual(self.account.credit_balance, Decimal('0.0'))
        self.assertEqual(self.account.last_topup_balance, Decimal('20.0'))

        load_account_credits(self.account, Decimal('10.0'))

        account = Account.objects.get(id=self.account.id)
        self.assertEqual(account.credit_balance, Decimal('10.0'))
        self.assertEqual(account.last_topup_balance, Decimal('10.0'))

        [transaction] = Transaction.objects.filter(
            account_number=self.account.account_number)

        self.assertEqual(transaction.status, Transaction.STATUS_COMPLETED)
        self.assertEqual(transaction.credit_amount, Decimal('10.0'))

        self.assertEqual(
            transaction.transaction_type,
            Transaction.TRANSACTION_TYPE_TOPUP)


class TestSummarize(GoDjangoTestCase):
    def setUp(self):
        self.vumi_helper = self.add_helper(DjangoVumiApiHelper())
        self.user_helper = self.vumi_helper.make_django_user()
        self.account = Account.objects.get(
            user=self.user_helper.get_django_user())

    def test_summarize(self):
        account = self.account

        mk_transaction(
            account,
            tag_name='a',
            message_cost=Decimal('1.0'),
            session_cost=Decimal('10.0'))

        mk_transaction(
            account,
            tag_name='b',
            message_cost=Decimal('3.0'),
            session_cost=Decimal('30.0'))

        mk_transaction(
            account,
            tag_name='a',
            message_cost=Decimal('1.0'),
            session_cost=Decimal('10.0'))

        mk_transaction(
            account,
            tag_name='b',
            message_cost=Decimal('4.0'),
            session_cost=Decimal('40.0'))

        mk_transaction(
            account,
            tag_name='c',
            message_cost=Decimal('5.0'),
            session_cost=Decimal('50.0'))

        result = summarize(
            Transaction.objects.all(),
            ('tag_name', 'message_cost'),
            ('message_cost', 'session_cost'))

        self.assertEqual(result, [{
            'tag_name': 'a',
            'count': 2,
            'message_cost': Decimal('1.0'),
            'total_message_cost': Decimal('2.0'),
            'total_session_cost': Decimal('20.0')
        }, {
            'tag_name': 'b',
            'count': 1,
            'message_cost': Decimal('3.0'),
            'total_message_cost': Decimal('3.0'),
            'total_session_cost': Decimal('30.0')
        }, {
            'tag_name': 'b',
            'count': 1,
            'message_cost': Decimal('4.0'),
            'total_message_cost': Decimal('4.0'),
            'total_session_cost': Decimal('40.0')
        }, {
            'tag_name': 'c',
            'count': 1,
            'message_cost': Decimal('5.0'),
            'total_message_cost': Decimal('5.0'),
            'total_session_cost': Decimal('50.0')
        }])

    def test_summarize_all_nones(self):
        account = self.account

        mk_transaction(
            account,
            tag_name='a',
            message_cost=None)

        mk_transaction(
            account,
            tag_name='a',
            message_cost=None)

        result = summarize(
            Transaction.objects.all(),
            ('tag_name', 'message_cost'),
            ('message_cost',))

        self.assertEqual(result, [{
            'tag_name': 'a',
            'count': 2,
            'message_cost': None,
            'total_message_cost': None,
        }])

    def test_summarize_some_nones(self):
        account = self.account

        mk_transaction(
            account,
            tag_name='a',
            message_cost=None)

        mk_transaction(
            account,
            tag_name='a',
            message_cost=Decimal('23.0'))

        result = summarize(
            Transaction.objects.all(),
            ('tag_name', 'message_cost'),
            ('message_cost',))

        self.assertEqual(result, [{
            'tag_name': 'a',
            'count': 1,
            'message_cost': None,
            'total_message_cost': None,
        }, {
            'tag_name': 'a',
            'count': 1,
            'message_cost': Decimal('23.0'),
            'total_message_cost': Decimal('23.0'),
        }])
