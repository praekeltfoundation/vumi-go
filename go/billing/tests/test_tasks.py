from datetime import date, datetime
from dateutil.relativedelta import relativedelta
import json

import mock
import moto

from go.base.tests.helpers import GoDjangoTestCase, DjangoVumiApiHelper
from go.base.s3utils import Bucket
from go.billing.models import (
    MessageCost, Account, Statement, Transaction, TransactionArchive)
from go.billing import tasks
from go.billing.django_utils import TransactionSerializer
from go.billing.tests.helpers import (
    this_month, mk_transaction, get_message_credits,
    get_session_credits, get_line_items)


class TestUtilityFunctions(GoDjangoTestCase):
    def test_month_range_today(self):
        from_date, to_date = tasks.month_range()
        self.assertEqual(to_date, from_date + relativedelta(months=1, days=-1))

    def test_month_range_specific_day(self):
        from_date, to_date = tasks.month_range(today=date(2014, 2, 1))
        self.assertEqual(from_date, date(2014, 1, 1))
        self.assertEqual(to_date, date(2014, 1, 31))

    def test_month_range_three_months_ago(self):
        from_date, to_date = tasks.month_range(3, today=date(2014, 2, 1))
        self.assertEqual(from_date, date(2013, 11, 1))
        self.assertEqual(to_date, date(2013, 11, 30))


class TestMonthlyStatementTask(GoDjangoTestCase):

    def setUp(self):
        self.vumi_helper = self.add_helper(DjangoVumiApiHelper())

        self.user_helper = self.vumi_helper.make_django_user()

        self.vumi_helper.setup_tagpool(u'pool1', [u'tag1'], {
            'delivery_class': 'ussd',
            'display_name': 'Pool 1'
        })
        self.user_helper.add_tagpool_permission(u'pool1')

        self.account = Account.objects.get(
            user=self.user_helper.get_django_user())

    @mock.patch('go.billing.tasks.generate_monthly_statement.s',
                new_callable=mock.MagicMock)
    def test_generate_monthly_statements(self, s):
        today = date.today()
        last_month = today - relativedelta(months=1)

        mk_transaction(
            self.account,
            created=last_month,
            last_modified=last_month)

        mk_transaction(
            self.account,
            message_direction=MessageCost.DIRECTION_OUTBOUND,
            created=last_month, last_modified=last_month)

        tasks.generate_monthly_account_statements()

        from_date = date(last_month.year, last_month.month, 1)
        to_date = date(today.year, today.month, 1) - relativedelta(days=1)
        s.assert_called_with(self.account.id, from_date, to_date)

    def test_generate_monthly_statement(self):
        result = tasks.generate_monthly_statement(
            self.account.id, *this_month())

        statement = Statement.objects.get(
            account=self.account, type=Statement.TYPE_MONTHLY)

        self.assertEqual(result, statement)

    def test_generate_monthly_statement_inbound_messages(self):
        mk_transaction(
            self.account,
            message_cost=100,
            markup_percent=10.0,
            message_direction=MessageCost.DIRECTION_INBOUND)

        mk_transaction(
            self.account,
            message_cost=100,
            markup_percent=10.0,
            message_direction=MessageCost.DIRECTION_OUTBOUND)

        mk_transaction(
            self.account,
            message_cost=100,
            markup_percent=10.0,
            message_direction=MessageCost.DIRECTION_INBOUND)

        statement = tasks.generate_monthly_statement(
            self.account.id, *this_month())

        [item] = get_line_items(statement).filter(
            description='Messages received')

        self.assertEqual(item.billed_by, 'Pool 1')
        self.assertEqual(item.channel, 'tag1')
        self.assertEqual(item.channel_type, 'USSD')
        self.assertEqual(item.units, 2)
        self.assertEqual(item.credits, get_message_credits(200, 10))
        self.assertEqual(item.unit_cost, 100)
        self.assertEqual(item.cost, 200)

    def test_generate_monthly_statement_outbound_messages(self):
        mk_transaction(
            self.account,
            message_cost=100,
            markup_percent=10.0,
            message_direction=MessageCost.DIRECTION_OUTBOUND)

        mk_transaction(
            self.account,
            message_cost=100,
            markup_percent=10.0,
            message_direction=MessageCost.DIRECTION_INBOUND)

        mk_transaction(
            self.account,
            message_cost=100,
            markup_percent=10.0,
            message_direction=MessageCost.DIRECTION_OUTBOUND)

        statement = tasks.generate_monthly_statement(
            self.account.id, *this_month())

        [item] = get_line_items(statement).filter(description='Messages sent')

        self.assertEqual(item.billed_by, 'Pool 1')
        self.assertEqual(item.channel, 'tag1')
        self.assertEqual(item.channel_type, 'USSD')
        self.assertEqual(item.units, 2)
        self.assertEqual(item.credits, get_message_credits(200, 10))
        self.assertEqual(item.unit_cost, 100)
        self.assertEqual(item.cost, 200)

    def test_generate_monthly_statement_different_message_costs(self):
        mk_transaction(self.account, message_cost=100, markup_percent=10.0)
        mk_transaction(self.account, message_cost=200, markup_percent=10.0)
        mk_transaction(self.account, message_cost=300, markup_percent=10.0)

        statement = tasks.generate_monthly_statement(
            self.account.id, *this_month())
        [item1, item2, item3] = get_line_items(statement).filter(
            description='Messages received')

        self.assertEqual(item1.credits, get_message_credits(100, 10))
        self.assertEqual(item1.unit_cost, 100)
        self.assertEqual(item1.cost, 100)

        self.assertEqual(item2.credits, get_message_credits(200, 10))
        self.assertEqual(item2.unit_cost, 200)
        self.assertEqual(item2.cost, 200)

        self.assertEqual(item3.credits, get_message_credits(300, 10))
        self.assertEqual(item3.unit_cost, 300)
        self.assertEqual(item3.cost, 300)

    def test_generate_monthly_statement_messages_different_markups(self):
        mk_transaction(self.account, message_cost=100, markup_percent=10.0)
        mk_transaction(self.account, message_cost=100, markup_percent=20.0)
        mk_transaction(self.account, message_cost=100, markup_percent=30.0)

        statement = tasks.generate_monthly_statement(
            self.account.id, *this_month())
        [item1, item2, item3] = get_line_items(statement).filter(
            description='Messages received')

        self.assertEqual(item1.credits, get_message_credits(100, 10))
        self.assertEqual(item2.credits, get_message_credits(100, 20))
        self.assertEqual(item3.credits, get_message_credits(100, 30))

    def test_generate_monthly_statement_different_session_costs(self):
        mk_transaction(
            self.account,
            session_created=True,
            session_cost=100,
            markup_percent=10.0)

        mk_transaction(
            self.account,
            session_created=True,
            session_cost=200,
            markup_percent=10.0)

        mk_transaction(
            self.account,
            session_created=True,
            session_cost=300,
            markup_percent=10.0)

        statement = tasks.generate_monthly_statement(
            self.account.id, *this_month())
        [item1, item2, item3] = get_line_items(statement).filter(
            description='Sessions')

        self.assertEqual(item1.credits, get_session_credits(100, 10))
        self.assertEqual(item1.unit_cost, 100)
        self.assertEqual(item1.cost, 100)

        self.assertEqual(item2.credits, get_session_credits(200, 10))
        self.assertEqual(item2.unit_cost, 200)
        self.assertEqual(item2.cost, 200)

        self.assertEqual(item3.credits, get_session_credits(300, 10))
        self.assertEqual(item3.unit_cost, 300)
        self.assertEqual(item3.cost, 300)

    def test_generate_monthly_statement_sessions_different_markups(self):
        mk_transaction(
            self.account,
            session_created=True,
            session_cost=100,
            markup_percent=10.0)

        mk_transaction(
            self.account,
            session_created=True,
            session_cost=100,
            markup_percent=20.0)

        mk_transaction(
            self.account,
            session_created=True,
            session_cost=100,
            markup_percent=30.0)

        statement = tasks.generate_monthly_statement(
            self.account.id, *this_month())
        [item1, item2, item3] = get_line_items(statement).filter(
            description='Sessions')

        self.assertEqual(item1.credits, get_session_credits(100, 10))
        self.assertEqual(item2.credits, get_session_credits(100, 20))
        self.assertEqual(item3.credits, get_session_credits(100, 30))

    def test_generate_monthly_statement_unaccessible_tags(self):
        self.vumi_helper.setup_tagpool(u'pool2', [u'tag2.1'], {
            'display_name': 'Pool 2'
        })

        mk_transaction(
            self.account,
            tag_pool_name=u'pool2',
            tag_name=u'tag2.1')

        statement = tasks.generate_monthly_statement(
            self.account.id, *this_month())

        [item] = get_line_items(statement).filter(channel=u'tag2.1')
        self.assertEqual(item.billed_by, 'Pool 2')


class TestArchiveTransactionsTask(GoDjangoTestCase):

    def setUp(self):
        self.vumi_helper = self.add_helper(DjangoVumiApiHelper())
        self.user_helper = self.vumi_helper.make_django_user()
        self.account = Account.objects.get(
            user=self.user_helper.get_django_user())

    def mk_bucket(self, config_name, defaults=None, **kw):
        defaults = defaults if defaults is not None else {
            "aws_access_key_id": "AWS-DUMMY-ID",
            "aws_secret_access_key": "AWS-DUMMY-SECRET",
        }
        go_s3_buckets = {config_name: defaults}
        go_s3_buckets[config_name].update(kw)
        self.vumi_helper.patch_settings(GO_S3_BUCKETS=go_s3_buckets)
        return Bucket(config_name)

    def assert_archive_in_s3(self, bucket, filename, transactions):
        s3_bucket = bucket.get_s3_bucket()
        key = s3_bucket.get_key(filename)
        data = key.get_contents_as_string().split("\n")
        # check for final newline
        self.assertEqual(data[-1], "")
        # construct expected JSON
        serializer = TransactionSerializer()
        expected_json = serializer.to_json(transactions)
        # check
        self.assertEqual(
            [json.loads(datum) for datum in data[:-1]],
            [json.loads(expected) for expected in expected_json])

    def assert_remaining_transactions(self, transactions):
        self.assertEqual(
            set(Transaction.objects.all()), set(transactions))

    @mock.patch('go.billing.tasks.archive_transactions.s',
                new_callable=mock.MagicMock)
    def test_archive_monthly_transactions(self, s):
        today = date.today()
        three_months_ago = today - relativedelta(months=3)

        mk_transaction(
            self.account,
            created=three_months_ago,
            last_modified=three_months_ago)

        mk_transaction(
            self.account,
            message_direction=MessageCost.DIRECTION_OUTBOUND,
            created=three_months_ago, last_modified=three_months_ago)

        tasks.archive_monthly_transactions()

        from_date = date(three_months_ago.year, three_months_ago.month, 1)
        to_date = from_date + relativedelta(months=1, days=-1)
        s.assert_called_with(self.account.id, from_date, to_date)

    @moto.mock_s3
    def test_archive_transactions(self):
        bucket = self.mk_bucket('billing.archive', s3_bucket_name='billing')
        bucket.create()
        from_time = datetime(2013, 11, 1)
        from_date, to_date = this_month(from_time.date())

        transaction = mk_transaction(self.account)
        transaction.created = from_time
        transaction.save()

        result = tasks.archive_transactions(
            self.account.id, from_date, to_date)

        archive = TransactionArchive.objects.get(account=self.account)

        self.assertEqual(result, archive)
        self.assertEqual(archive.account, self.account)
        self.assertEqual(
            archive.filename,
            "transactions-test-0-user-2013-11-01-to-2013-11-30.json")
        self.assertEqual(archive.from_date, from_date)
        self.assertEqual(archive.to_date, to_date)
        self.assertEqual(archive.status, archive.STATUS_ARCHIVE_COMPLETED)

        self.assert_remaining_transactions([])
        self.assert_archive_in_s3(bucket, archive.filename, [transaction])

    @moto.mock_s3
    def test_archive_transactions_complex(self):
        bucket = self.mk_bucket('billing.archive', s3_bucket_name='billing')
        bucket.create()
        from_time = datetime(2013, 11, 1)
        before_time = datetime(2013, 10, 31, 12, 59, 59)
        after_time = datetime(2013, 12, 1, 0, 0, 0)
        from_date, to_date = this_month(from_time.date())

        def mk_transaction_set(n, created):
            transaction_set = set()
            for i in range(5):
                transaction = mk_transaction(self.account)
                transaction.created = created
                transaction.save()
                transaction_set.add(transaction)
            return transaction_set

        transactions_before = mk_transaction_set(5, before_time)
        transactions_after = mk_transaction_set(5, after_time)
        transactions_within = mk_transaction_set(10, from_time)

        result = tasks.archive_transactions(
            self.account.id, from_date, to_date)

        archive = TransactionArchive.objects.get(account=self.account)

        self.assertEqual(result, archive)
        self.assertEqual(archive.account, self.account)
        self.assertEqual(
            archive.filename,
            "transactions-test-0-user-2013-11-01-to-2013-11-30.json")
        self.assertEqual(archive.from_date, from_date)
        self.assertEqual(archive.to_date, to_date)
        self.assertEqual(archive.status, archive.STATUS_ARCHIVE_COMPLETED)

        self.assert_remaining_transactions(
            transactions_before | transactions_after)
        self.assert_archive_in_s3(
            bucket, archive.filename,
            sorted(transactions_within, key=lambda trans: trans.pk))
