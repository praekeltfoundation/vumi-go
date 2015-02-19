from datetime import date, datetime
from dateutil.relativedelta import relativedelta
from decimal import Decimal
import gzip
import json
import StringIO

from django.core import mail

import mock

from go.base.s3utils import Bucket
from go.base.utils import vumi_api_for_user
from go.base.tests.helpers import GoDjangoTestCase, DjangoVumiApiHelper
from go.base.tests.s3_helpers import S3Helper

from go.billing.models import (
    MessageCost, Account, Statement, Transaction, TransactionArchive,
    LowCreditNotification)
from go.billing import tasks
from go.billing.django_utils import TransactionSerializer
from go.billing.tests.helpers import (
    this_month, mk_transaction, get_line_items,
    get_message_credits, get_session_credits, get_storage_credits,
    get_session_length_credits)


def gunzip(data):
    """ Gunzip data. """
    return gzip.GzipFile(fileobj=StringIO.StringIO(data)).read()


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

        self.vumi_helper.setup_tagpool(u'pool1', [u'tag1', u'tag2'], {
            'delivery_class': 'ussd',
            'display_name': 'Pool 1'
        })

        self.vumi_helper.setup_tagpool(u'pool2', [u'tag1'])

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

    def test_generate_monthly_statement_unknown_tagpool(self):
        mk_transaction(
            self.account,
            tag_name=u'unknown-tag',
            tag_pool_name=u'unknown-tagpool',
            message_direction=MessageCost.DIRECTION_INBOUND)

        statement = tasks.generate_monthly_statement(
            self.account.id, *this_month())

        items = get_line_items(statement).filter(billed_by='unknown-tagpool')
        item = items.latest('id')
        self.assertEqual(item.channel, 'unknown-tag')
        self.assertEqual(item.channel_type, None)

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

        [item] = get_line_items(statement).filter(
            description='Messages sent')

        self.assertEqual(item.billed_by, 'Pool 1')
        self.assertEqual(item.channel, 'tag1')
        self.assertEqual(item.channel_type, 'USSD')
        self.assertEqual(item.units, 2)
        self.assertEqual(item.credits, get_message_credits(200, 10))
        self.assertEqual(item.unit_cost, 100)
        self.assertEqual(item.cost, 200)

    @mock.patch('go.billing.settings.SYSTEM_BILLER_NAME', 'Serenity')
    def test_generate_monthly_statement_storage_cost(self):
        mk_transaction(
            self.account,
            tag_pool_name=u'pool1',
            tag_name=u'tag1',
            storage_cost=100,
            markup_percent=10.0)

        mk_transaction(
            self.account,
            tag_pool_name=u'pool1',
            tag_name=u'tag2',
            storage_cost=100,
            markup_percent=10.0)

        mk_transaction(
            self.account,
            tag_pool_name=u'pool2',
            tag_name=u'tag1',
            storage_cost=100,
            markup_percent=10.0)

        statement = tasks.generate_monthly_statement(
            self.account.id, *this_month())

        [item] = get_line_items(statement).filter(description='Storage cost')

        self.assertEqual(item.billed_by, 'Serenity')
        self.assertEqual(item.channel, None)
        self.assertEqual(item.channel_type, None)
        self.assertEqual(item.units, 3)
        self.assertEqual(item.credits, get_storage_credits(300, 10))
        self.assertEqual(item.unit_cost, 100)
        self.assertEqual(item.cost, 300)

    def test_generate_monthly_statement_different_message_costs(self):
        mk_transaction(
            account=self.account,
            message_cost=100,
            markup_percent=10.0)

        mk_transaction(
            account=self.account,
            message_cost=200,
            markup_percent=10.0)

        mk_transaction(
            account=self.account,
            message_cost=300,
            markup_percent=10.0)

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
        mk_transaction(
            account=self.account,
            message_cost=100,
            markup_percent=10.0)

        mk_transaction(
            account=self.account,
            message_cost=100,
            markup_percent=20.0)

        mk_transaction(
            account=self.account,
            message_cost=100,
            markup_percent=30.0)

        statement = tasks.generate_monthly_statement(
            self.account.id, *this_month())
        [item1, item2, item3] = get_line_items(statement).filter(
            description='Messages received')

        self.assertEqual(item1.credits, get_message_credits(100, 10))
        self.assertEqual(item2.credits, get_message_credits(100, 20))
        self.assertEqual(item3.credits, get_message_credits(100, 30))

    def test_generate_monthly_statement_different_storage_costs(self):
        mk_transaction(self.account, storage_cost=100, markup_percent=10.0)
        mk_transaction(self.account, storage_cost=200, markup_percent=10.0)
        mk_transaction(self.account, storage_cost=300, markup_percent=10.0)

        statement = tasks.generate_monthly_statement(
            self.account.id, *this_month())
        [item1, item2, item3] = get_line_items(statement).filter(
            description='Storage cost')

        self.assertEqual(item1.credits, get_storage_credits(100, 10))
        self.assertEqual(item1.unit_cost, 100)
        self.assertEqual(item1.cost, 100)

        self.assertEqual(item2.credits, get_storage_credits(200, 10))
        self.assertEqual(item2.unit_cost, 200)
        self.assertEqual(item2.cost, 200)

        self.assertEqual(item3.credits, get_storage_credits(300, 10))
        self.assertEqual(item3.unit_cost, 300)
        self.assertEqual(item3.cost, 300)

    def test_generate_monthly_statement_storage_different_markups(self):
        mk_transaction(self.account, storage_cost=100, markup_percent=10.0)
        mk_transaction(self.account, storage_cost=100, markup_percent=20.0)
        mk_transaction(self.account, storage_cost=100, markup_percent=30.0)

        statement = tasks.generate_monthly_statement(
            self.account.id, *this_month())
        [item1, item2, item3] = get_line_items(statement).filter(
            description='Storage cost')

        self.assertEqual(item1.credits, get_storage_credits(100, 10))
        self.assertEqual(item2.credits, get_storage_credits(100, 20))
        self.assertEqual(item3.credits, get_storage_credits(100, 30))

    def test_generate_monthly_statement_storage_none_storage_cost(self):
        mk_transaction(
            self.account,
            storage_cost=None)

        statement = tasks.generate_monthly_statement(
            self.account.id, *this_month())

        [item] = get_line_items(statement).filter(
            description='Storage cost')

        self.assertEqual(item.credits, None)
        self.assertEqual(item.unit_cost, 0)
        self.assertEqual(item.cost, 0)

    def test_generate_monthly_statement_storage_none_markup(self):
        mk_transaction(
            self.account,
            storage_cost=100,
            markup_percent=None)

        statement = tasks.generate_monthly_statement(
            self.account.id, *this_month())

        [item] = get_line_items(statement).filter(
            description='Storage cost')

        self.assertEqual(item.credits, None)
        self.assertEqual(item.unit_cost, 100)
        self.assertEqual(item.cost, 100)

    def test_generate_monthly_statement_sessions(self):
        mk_transaction(
            self.account,
            session_created=True,
            session_cost=100,
            markup_percent=10.0)

        mk_transaction(
            self.account,
            session_created=True,
            session_cost=100,
            markup_percent=10.0)

        mk_transaction(
            self.account,
            session_created=True,
            session_cost=100,
            markup_percent=10.0)

        statement = tasks.generate_monthly_statement(
            self.account.id, *this_month())
        [item] = get_line_items(statement).filter(
            description='Sessions (billed per session)')

        self.assertEqual(item.credits, get_session_credits(300, 10))
        self.assertEqual(item.unit_cost, 100)
        self.assertEqual(item.cost, 300)

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
            description='Sessions (billed per session)')

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
            description='Sessions (billed per session)')

        self.assertEqual(item1.credits, get_session_credits(100, 10))
        self.assertEqual(item2.credits, get_session_credits(100, 20))
        self.assertEqual(item3.credits, get_session_credits(100, 30))

    def test_generate_monthly_statement_session_length(self):
        mk_transaction(
            self.account,
            session_unit_time=20,
            session_unit_cost=100,
            session_length_cost=100,
            markup_percent=10.0)

        mk_transaction(
            self.account,
            session_unit_time=20,
            session_unit_cost=100,
            session_length_cost=200,
            markup_percent=10.0)

        mk_transaction(
            self.account,
            session_unit_time=20,
            session_unit_cost=100,
            session_length_cost=300,
            markup_percent=10.0)

        statement = tasks.generate_monthly_statement(
            self.account.id, *this_month())
        [item] = get_line_items(statement).filter(
            description='Session intervals (billed per 20s)')

        self.assertEqual(item.credits, get_session_length_credits(600, 10))
        self.assertEqual(item.unit_cost, 100)
        self.assertEqual(item.cost, 600)
        self.assertEqual(item.units, 6)

    def test_generate_monthly_statement_different_session_unit_times(self):
        mk_transaction(
            self.account,
            session_unit_time=20,
            session_unit_cost=100,
            session_length_cost=100,
            markup_percent=10.0)

        mk_transaction(
            self.account,
            session_unit_time=21,
            session_unit_cost=100,
            session_length_cost=100,
            markup_percent=10.0)

        mk_transaction(
            self.account,
            session_unit_time=22,
            session_unit_cost=100,
            session_length_cost=100,
            markup_percent=10.0)

        statement = tasks.generate_monthly_statement(
            self.account.id, *this_month())
        [item1, item2, item3] = get_line_items(statement).filter(
            description__startswith='Session intervals')

        self.assertEqual(item1.credits, get_session_length_credits(100, 10))
        self.assertEqual(item1.unit_cost, 100)
        self.assertEqual(item1.cost, 100)
        self.assertEqual(item1.units, 1)

        self.assertEqual(
            item1.description,
            'Session intervals (billed per 20s)')

        self.assertEqual(item2.credits, get_session_length_credits(100, 10))
        self.assertEqual(item2.unit_cost, 100)
        self.assertEqual(item2.cost, 100)
        self.assertEqual(item2.units, 1)

        self.assertEqual(
            item2.description,
            'Session intervals (billed per 21s)')

        self.assertEqual(item3.credits, get_session_length_credits(100, 10))
        self.assertEqual(item3.unit_cost, 100)
        self.assertEqual(item3.cost, 100)
        self.assertEqual(item3.units, 1)

        self.assertEqual(
            item3.description,
            'Session intervals (billed per 22s)')

    def test_generate_monthly_statement_different_session_unit_costs(self):
        mk_transaction(
            self.account,
            session_unit_time=20,
            session_unit_cost=100,
            session_length_cost=100,
            markup_percent=10.0)

        mk_transaction(
            self.account,
            session_unit_time=20,
            session_unit_cost=200,
            session_length_cost=200,
            markup_percent=10.0)

        mk_transaction(
            self.account,
            session_unit_time=20,
            session_unit_cost=300,
            session_length_cost=600,
            markup_percent=10.0)

        statement = tasks.generate_monthly_statement(
            self.account.id, *this_month())
        [item1, item2, item3] = get_line_items(statement).filter(
            description='Session intervals (billed per 20s)')

        self.assertEqual(item1.credits, get_session_length_credits(100, 10))
        self.assertEqual(item1.unit_cost, 100)
        self.assertEqual(item1.cost, 100)
        self.assertEqual(item1.units, 1)

        self.assertEqual(item2.credits, get_session_length_credits(200, 10))
        self.assertEqual(item2.unit_cost, 200)
        self.assertEqual(item2.cost, 200)
        self.assertEqual(item2.units, 1)

        self.assertEqual(item3.credits, get_session_length_credits(600, 10))
        self.assertEqual(item3.unit_cost, 300)
        self.assertEqual(item3.cost, 600)
        self.assertEqual(item3.units, 2)

    def test_generate_monthly_statement_session_length_different_markups(self):
        mk_transaction(
            self.account,
            session_unit_time=20,
            session_unit_cost=100,
            session_length_cost=100,
            markup_percent=10.0)

        mk_transaction(
            self.account,
            session_unit_time=20,
            session_unit_cost=100,
            session_length_cost=100,
            markup_percent=11.0)

        mk_transaction(
            self.account,
            session_unit_time=20,
            session_unit_cost=100,
            session_length_cost=100,
            markup_percent=12.0)

        statement = tasks.generate_monthly_statement(
            self.account.id, *this_month())
        [item1, item2, item3] = get_line_items(statement).filter(
            description='Session intervals (billed per 20s)')

        self.assertEqual(item1.credits, get_session_length_credits(100, 10))
        self.assertEqual(item1.unit_cost, 100)
        self.assertEqual(item1.cost, 100)
        self.assertEqual(item1.units, 1)

        self.assertEqual(item2.credits, get_session_length_credits(100, 11))
        self.assertEqual(item2.unit_cost, 100)
        self.assertEqual(item2.cost, 100)
        self.assertEqual(item2.units, 1)

        self.assertEqual(item3.credits, get_session_length_credits(100, 12))
        self.assertEqual(item3.unit_cost, 100)
        self.assertEqual(item3.cost, 100)
        self.assertEqual(item3.units, 1)

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

        item = get_line_items(statement).filter(channel=u'tag2.1').latest('id')
        self.assertEqual(item.billed_by, 'Pool 2')

    def test_generate_monthly_statement_messages_none_message_cost(self):
        mk_transaction(
            self.account,
            message_cost=None)

        statement = tasks.generate_monthly_statement(
            self.account.id, *this_month())

        [item] = get_line_items(statement).filter(
            description='Messages received')

        self.assertEqual(item.credits, None)
        self.assertEqual(item.unit_cost, 0)
        self.assertEqual(item.cost, 0)

    def test_generate_monthly_statement_messages_none_markup(self):
        mk_transaction(
            self.account,
            message_cost=100,
            markup_percent=None)

        statement = tasks.generate_monthly_statement(
            self.account.id, *this_month())

        [item] = get_line_items(statement).filter(
            description='Messages received')

        self.assertEqual(item.credits, None)
        self.assertEqual(item.unit_cost, 100)
        self.assertEqual(item.cost, 100)

    def test_generate_monthly_statement_sessions_none_session_cost(self):
        mk_transaction(
            self.account,
            session_cost=None,
            session_created=True)

        statement = tasks.generate_monthly_statement(
            self.account.id, *this_month())

        [item] = get_line_items(statement).filter(
            description='Sessions (billed per session)')

        self.assertEqual(item.credits, None)
        self.assertEqual(item.unit_cost, 0)
        self.assertEqual(item.cost, 0)

    def test_generate_monthly_statement_sessions_none_markup(self):
        mk_transaction(
            self.account,
            session_cost=100,
            markup_percent=None,
            session_created=True)

        statement = tasks.generate_monthly_statement(
            self.account.id, *this_month())

        [item] = get_line_items(statement).filter(
            description='Sessions (billed per session)')

        self.assertEqual(item.credits, None)
        self.assertEqual(item.unit_cost, 100)
        self.assertEqual(item.cost, 100)

    def test_generate_monthly_statement_irrelevant_transaction_types(self):
        mk_transaction(
            self.account,
            transaction_type=Transaction.TRANSACTION_TYPE_TOPUP,
            message_cost=1.0,
            storage_cost=2.0,
            session_cost=3.0,
            session_created=True)

        mk_transaction(
            self.account,
            transaction_type=None,
            message_cost=1.0,
            storage_cost=2.0,
            session_cost=3.0,
            session_created=True)

        statement = tasks.generate_monthly_statement(
            self.account.id, *this_month())

        self.assertEqual(len(get_line_items(statement)), 0)

    @mock.patch('go.billing.settings.PROVIDERS', {
        'provider1': 'Provider 1',
        'provider2': 'Provider 2',
    })
    def test_generate_monthly_statement_providers_inbound(self):
        mk_transaction(
            self.account,
            provider='provider1',
            message_cost=100,
            markup_percent=10.0,
            message_direction=MessageCost.DIRECTION_INBOUND)

        mk_transaction(
            self.account,
            provider='provider2',
            message_cost=100,
            markup_percent=10.0,
            message_direction=MessageCost.DIRECTION_INBOUND)

        mk_transaction(
            self.account,
            provider='provider1',
            message_cost=100,
            markup_percent=10.0,
            message_direction=MessageCost.DIRECTION_INBOUND)

        statement = tasks.generate_monthly_statement(
            self.account.id, *this_month())

        [item1, item2] = get_line_items(statement).filter(
            description__startswith='Messages received')

        self.assertEqual(item1.description, 'Messages received - Provider 1')
        self.assertEqual(item1.units, 2)

        self.assertEqual(item2.description, 'Messages received - Provider 2')
        self.assertEqual(item2.units, 1)

    @mock.patch('go.billing.settings.PROVIDERS', {'provider1': 'Provider 1'})
    def test_generate_monthly_statement_unknown_provider_inbound(self):
        mk_transaction(
            self.account,
            provider='provider2',
            message_cost=100,
            markup_percent=10.0,
            message_direction=MessageCost.DIRECTION_INBOUND)

        statement = tasks.generate_monthly_statement(
            self.account.id, *this_month())

        [item] = get_line_items(statement).filter(
            description__startswith='Messages received')

        self.assertEqual(item.description, 'Messages received - provider2')

    def test_generate_monthly_statement_no_provider_inbound(self):
        mk_transaction(
            self.account,
            provider=None,
            message_cost=100,
            markup_percent=10.0,
            message_direction=MessageCost.DIRECTION_INBOUND)

        statement = tasks.generate_monthly_statement(
            self.account.id, *this_month())

        [item] = get_line_items(statement).filter(
            description__startswith='Messages received')

        self.assertEqual(
            item.description,
            'Messages received')

    @mock.patch('go.billing.settings.PROVIDERS', {
        'provider1': 'Provider 1',
        'provider2': 'Provider 2',
    })
    def test_generate_monthly_statement_providers_outbound(self):
        mk_transaction(
            self.account,
            provider='provider1',
            message_cost=100,
            markup_percent=10.0,
            message_direction=MessageCost.DIRECTION_OUTBOUND)

        mk_transaction(
            self.account,
            provider='provider2',
            message_cost=100,
            markup_percent=10.0,
            message_direction=MessageCost.DIRECTION_OUTBOUND)

        mk_transaction(
            self.account,
            provider='provider1',
            message_cost=100,
            markup_percent=10.0,
            message_direction=MessageCost.DIRECTION_OUTBOUND)

        statement = tasks.generate_monthly_statement(
            self.account.id, *this_month())

        [item1, item2] = get_line_items(statement).filter(
            description__startswith='Messages sent')

        self.assertEqual(item1.description, 'Messages sent - Provider 1')
        self.assertEqual(item1.units, 2)

        self.assertEqual(item2.description, 'Messages sent - Provider 2')
        self.assertEqual(item2.units, 1)

    @mock.patch('go.billing.settings.PROVIDERS', {'provider1': 'Provider 1'})
    def test_generate_monthly_statement_unknown_provider_outbound(self):
        mk_transaction(
            self.account,
            provider='provider2',
            message_cost=100,
            markup_percent=10.0,
            message_direction=MessageCost.DIRECTION_OUTBOUND)

        statement = tasks.generate_monthly_statement(
            self.account.id, *this_month())

        [item] = get_line_items(statement).filter(
            description__startswith='Messages sent')

        self.assertEqual(item.description, 'Messages sent - provider2')

    def test_generate_monthly_statement_no_provider_outbound(self):
        mk_transaction(
            self.account,
            provider=None,
            message_cost=100,
            markup_percent=10.0,
            message_direction=MessageCost.DIRECTION_OUTBOUND)

        statement = tasks.generate_monthly_statement(
            self.account.id, *this_month())

        [item] = get_line_items(statement).filter(
            description__startswith='Messages sent')

        self.assertEqual(
            item.description,
            'Messages sent')

    @mock.patch('go.billing.settings.PROVIDERS', {
        'provider1': 'Provider 1',
        'provider2': 'Provider 2',
    })
    def test_generate_monthly_statement_providers_sessions(self):
        mk_transaction(
            self.account,
            provider='provider1',
            session_cost=100,
            session_created=True)

        mk_transaction(
            self.account,
            provider='provider2',
            session_cost=100,
            session_created=True)

        mk_transaction(
            self.account,
            provider='provider1',
            session_cost=100,
            session_created=True)

        statement = tasks.generate_monthly_statement(
            self.account.id, *this_month())

        [item1, item2] = get_line_items(statement).filter(
            description__startswith='Sessions (billed per session)')

        self.assertEqual(
            item1.description,
            'Sessions (billed per session) - Provider 1')

        self.assertEqual(item1.units, 2)

        self.assertEqual(
            item2.description,
            'Sessions (billed per session) - Provider 2')

        self.assertEqual(item2.units, 1)


class TestArchiveTransactionsTask(GoDjangoTestCase):

    def setUp(self):
        self.vumi_helper = self.add_helper(DjangoVumiApiHelper())
        self.s3_helper = self.add_helper(S3Helper(self.vumi_helper))
        self.user_helper = self.vumi_helper.make_django_user()
        self.account = Account.objects.get(
            user=self.user_helper.get_django_user())

    def assert_archive_in_s3(self, bucket, filename, transactions):
        s3_bucket = bucket.get_s3_bucket()
        key = s3_bucket.get_key(filename)
        data = gunzip(key.get_contents_as_string()).split("\n")
        # check for final newline
        self.assertEqual(data[-1], "")
        # construct expected JSON
        serializer = TransactionSerializer()
        expected_json = serializer.to_json(transactions)

        def tuplify(d):
            if isinstance(d, dict):
                return tuple(sorted(
                    (k, tuplify(v)) for k, v in d.iteritems()))
            return d

        # check transactions
        self.assertEqual(
            set(tuplify(json.loads(datum)) for datum in data[:-1]),
            set(tuplify(json.loads(expected)) for expected in expected_json))

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

    def test_archive_transactions(self):
        self.s3_helper.patch_settings(
            'billing.archive', s3_bucket_name='billing')
        bucket = Bucket('billing.archive')
        bucket.create()
        from_time = datetime(2013, 11, 1)
        from_date, to_date = this_month(from_time.date())

        transaction = mk_transaction(self.account, created=from_time)

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

    def test_archive_transactions_upload_only(self):
        self.s3_helper.patch_settings(
            'billing.archive', s3_bucket_name='billing')
        bucket = Bucket('billing.archive')
        bucket.create()
        from_time = datetime(2013, 11, 1)
        from_date, to_date = this_month(from_time.date())

        transaction = mk_transaction(self.account, created=from_time)

        result = tasks.archive_transactions(
            self.account.id, from_date, to_date, delete=False)

        archive = TransactionArchive.objects.get(account=self.account)

        self.assertEqual(result, archive)
        self.assertEqual(archive.account, self.account)
        self.assertEqual(
            archive.filename,
            "transactions-test-0-user-2013-11-01-to-2013-11-30.json")
        self.assertEqual(archive.from_date, from_date)
        self.assertEqual(archive.to_date, to_date)
        self.assertEqual(archive.status, archive.STATUS_TRANSACTIONS_UPLOADED)

        self.assert_remaining_transactions([transaction])
        self.assert_archive_in_s3(bucket, archive.filename, [transaction])

    def test_archive_transactions_complex(self):
        self.s3_helper.patch_settings(
            'billing.archive', s3_bucket_name='billing')
        bucket = Bucket('billing.archive')
        bucket.create()
        from_time = datetime(2013, 11, 1)
        before_time = datetime(2013, 10, 31, 12, 59, 59)
        after_time = datetime(2013, 12, 1, 0, 0, 0)
        from_date, to_date = this_month(from_time.date())

        def mk_transaction_set(n, created):
            transaction_set = set()
            for i in range(n):
                transaction = mk_transaction(self.account, created=created)
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
            bucket, archive.filename, transactions_within)


class TestGenStatementThenArchiveMonthlyTask(GoDjangoTestCase):

    def setUp(self):
        self.vumi_helper = self.add_helper(DjangoVumiApiHelper())

        user1_helper = self.vumi_helper.make_django_user('user1')
        user2_helper = self.vumi_helper.make_django_user('user2')

        self.account1 = Account.objects.get(
            user=user1_helper.get_django_user())

        self.account2 = Account.objects.get(
            user=user2_helper.get_django_user())

        self.monkey_patch(Bucket, 'upload', lambda *a, **kw: None)

    def test_gen_statement_then_archive_monthly(self):
        tasks.gen_statement_then_archive_monthly()
        [statement1] = Statement.objects.filter(account=self.account1)
        [statement2] = Statement.objects.filter(account=self.account2)
        [archive1] = TransactionArchive.objects.filter(account=self.account1)
        [archive2] = TransactionArchive.objects.filter(account=self.account2)

        from_date, to_date = tasks.month_range(months_ago=1)
        self.assertEqual(statement1.from_date, from_date)
        self.assertEqual(statement1.to_date, to_date)

        self.assertEqual(statement2.from_date, from_date)
        self.assertEqual(statement2.to_date, to_date)

        self.assertEqual(archive1.from_date, from_date)
        self.assertEqual(archive1.to_date, to_date)

        self.assertEqual(archive2.from_date, from_date)
        self.assertEqual(archive2.to_date, to_date)

    def test_gen_statement_then_archive_monthly_existing_statement(self):
        from_date, to_date = tasks.month_range(months_ago=1)
        tasks.generate_monthly_statement(self.account1.id, from_date, to_date)
        tasks.generate_monthly_statement(self.account2.id, from_date, to_date)

        statements = Statement.objects
        archives = TransactionArchive.objects

        self.assertEqual(len(statements.filter(account=self.account1)), 1)
        self.assertEqual(len(statements.filter(account=self.account2)), 1)

        tasks.gen_statement_then_archive_monthly()
        self.assertEqual(len(statements.filter(account=self.account1)), 1)
        self.assertEqual(len(statements.filter(account=self.account2)), 1)
        self.assertEqual(len(archives.filter(account=self.account1)), 0)
        self.assertEqual(len(archives.filter(account=self.account2)), 0)

    def test_gen_statement_then_archive_monthly_existing_archive(self):
        from_date, to_date = tasks.month_range(months_ago=1)
        tasks.archive_transactions(
            self.account1.id, from_date, to_date, delete=False)
        tasks.archive_transactions(
            self.account2.id, from_date, to_date, delete=False)

        statements = Statement.objects
        archives = TransactionArchive.objects

        self.assertEqual(len(archives.filter(account=self.account1)), 1)
        self.assertEqual(len(archives.filter(account=self.account2)), 1)

        tasks.gen_statement_then_archive_monthly()
        self.assertEqual(len(statements.filter(account=self.account1)), 0)
        self.assertEqual(len(statements.filter(account=self.account2)), 0)
        self.assertEqual(len(archives.filter(account=self.account1)), 1)
        self.assertEqual(len(archives.filter(account=self.account2)), 1)


class TestGenStatementThenArchiveTask(GoDjangoTestCase):

    def setUp(self):
        self.vumi_helper = self.add_helper(DjangoVumiApiHelper())
        self.user_helper = self.vumi_helper.make_django_user()

        self.account = Account.objects.get(
            user=self.user_helper.get_django_user())

        self.monkey_patch(Bucket, 'upload', lambda *a, **kw: None)

    def test_gen_statement_then_archive(self):
        from_date, to_date = tasks.month_range(months_ago=3)
        tasks.gen_statement_then_archive(self.account.id, from_date, to_date)

        [statement] = Statement.objects.filter(account=self.account)
        [archive] = TransactionArchive.objects.filter(account=self.account)

        self.assertEqual(statement.from_date, from_date)
        self.assertEqual(statement.to_date, to_date)

        self.assertEqual(archive.from_date, from_date)
        self.assertEqual(archive.to_date, to_date)

    def test_gen_statement_then_archive_delete(self):
        from_date, to_date = tasks.month_range(months_ago=3)

        mk_transaction(
            self.account,
            created=from_date,
            last_modified=from_date)

        self.assertEqual(len(Transaction.objects.all()), 1)
        tasks.gen_statement_then_archive(self.account.id, from_date, to_date)
        self.assertEqual(len(Transaction.objects.all()), 0)

    def test_gen_statement_then_archive_no_delete(self):
        from_date, to_date = tasks.month_range(months_ago=3)

        mk_transaction(
            self.account,
            created=from_date,
            last_modified=from_date)

        self.assertEqual(len(Transaction.objects.all()), 1)

        tasks.gen_statement_then_archive(
            self.account.id,
            from_date,
            to_date,
            delete=False)

        self.assertEqual(len(Transaction.objects.all()), 1)


class TestLowCreditNotificationTask(GoDjangoTestCase):
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
        percent = Decimal(percent)
        balance = Decimal(balance)
        return tasks.create_low_credit_notification(
            self.acc.account_number, percent, balance)

    def test_confirm_sent(self):
        notification_id, res = self.mk_notification('0.60', '31.41')
        notification = LowCreditNotification.objects.get(pk=notification_id)
        timestamp = res.get()
        self.assertEqual(timestamp, notification.success)

    def test_email_sent(self):
        notification_id, res = self.mk_notification('0.701', '1234.5678')
        notification = LowCreditNotification.objects.get(pk=notification_id)
        self.assertTrue(res.get() is not None)
        self.assertEqual(len(mail.outbox), 1)
        [email] = mail.outbox

        self.assertEqual(email.recipients(), [self.django_user.email])
        self.assertEqual(email.from_email, 'support@vumi.org')
        self.assertEqual(
            'Vumi Go account %s (%s) at %s%% left of available credits' % (
                str(self.acc.user.email), str(self.acc.user.get_full_name()),
                '70.100'),
            email.subject)
        self.assertTrue('29.900%' in email.body)
        self.assertTrue('1,234.56 credits' in email.body)
        self.assertTrue(self.django_user.get_full_name() in email.body)
        self.assertTrue(str(notification.pk) in email.body)
        self.assertTrue(str(self.acc.user.email) in email.body)


class TestLoadCreditsForDeveloperAccount(GoDjangoTestCase):
    def setUp(self):
        self.vumi_helper = self.add_helper(DjangoVumiApiHelper())
        self.user_helper = self.vumi_helper.make_django_user()
        self.user_account = self.user_helper.get_user_account()

    def _set_developer_flag(self, user, value):
        self.user_account.is_developer = value
        self.user_account.save()

    def _assert_account_balance(self, balance):
        account = Account.objects.get(account_number=self.user_account.key)
        self.assertEqual(account.credit_balance, balance)

    def _assert_last_transaction_topup(self, credits):
        transaction = Transaction.objects.order_by('-created')[0]
        self.assertEqual(
            transaction.transaction_type, Transaction.TRANSACTION_TYPE_TOPUP)
        self.assertEqual(transaction.credit_amount, credits)

    def test_set_credit_balance(self):
        self._assert_account_balance(0.0)
        tasks.set_account_balance(self.user_account.key, 10.0)
        self._assert_account_balance(10.0)
        self._assert_last_transaction_topup(10.0)

    def test_set_all_developer_account_balances(self):
        self._assert_account_balance(0.0)
        tasks.set_developer_account_balances(10.0)
        self._assert_account_balance(0.0)
        self.assertEqual(Transaction.objects.count(), 0)

        self._set_developer_flag(self.user_helper.get_django_user(), True)
        tasks.set_developer_account_balances(10.0)
        self._assert_account_balance(10.0)
        self._assert_last_transaction_topup(10.0)
