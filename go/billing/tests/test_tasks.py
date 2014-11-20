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
from go.billing.tests.helpers import this_month, mk_transaction


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
            message_direction=MessageCost.DIRECTION_INBOUND)

        mk_transaction(
            self.account,
            message_direction=MessageCost.DIRECTION_OUTBOUND)

        mk_transaction(
            self.account,
            message_direction=MessageCost.DIRECTION_INBOUND)

        statement = tasks.generate_monthly_statement(
            self.account.id, *this_month())
        [item] = statement.lineitem_set.filter(
            description='Messages received (including sessions)')

        self.assertEqual(item.billed_by, 'Pool 1')
        self.assertEqual(item.channel, 'tag1')
        self.assertEqual(item.channel_type, 'USSD')
        self.assertEqual(item.units, 2)
        self.assertEqual(item.credits, 56)
        self.assertEqual(item.unit_cost, 100)
        self.assertEqual(item.cost, 200)

    def test_generate_monthly_statement_outbound_messages(self):
        mk_transaction(
            self.account,
            message_direction=MessageCost.DIRECTION_OUTBOUND)

        mk_transaction(
            self.account,
            message_direction=MessageCost.DIRECTION_INBOUND)

        mk_transaction(
            self.account,
            message_direction=MessageCost.DIRECTION_OUTBOUND)

        statement = tasks.generate_monthly_statement(
            self.account.id, *this_month())
        [item] = statement.lineitem_set.filter(
            description='Messages sent (including sessions)')

        self.assertEqual(item.billed_by, 'Pool 1')
        self.assertEqual(item.channel, 'tag1')
        self.assertEqual(item.channel_type, 'USSD')
        self.assertEqual(item.units, 2)
        self.assertEqual(item.credits, 56)
        self.assertEqual(item.unit_cost, 100)
        self.assertEqual(item.cost, 200)


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

        transactions = Transaction.objects.all()
        self.assertEqual(list(transactions), [])

        s3_bucket = bucket.get_s3_bucket()
        key = s3_bucket.get_key(archive.filename)
        contents = key.get_contents_as_string()
        self.maxDiff = None
        self.assertEqual(json.loads(contents[:-1]), {
            u"pk": transaction.pk,
            u"model": u"billing.transaction",
            u"fields": {
                u"account_number": self.account.account_number,
                u"created": unicode(transaction.created.isoformat()[:23]),
                u"last_modified": unicode(
                    transaction.last_modified.isoformat()[:23]),
                u"credit_amount": u"28",
                u"credit_factor": u"0.25",
                u"markup_percent": u"10",
                u"message_cost": u"100",
                u"message_direction": u"Inbound",
                u"message_id": None,
                u"session_cost": u"0",
                u"session_created": None,
                u"status": u"Completed",
                u"tag_pool_name": u"pool1",
                u"tag_name": u"tag1",
            },
        })
        self.assertEqual(contents[-1], "\n")
