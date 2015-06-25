from decimal import Decimal
from datetime import date

from go.base.tests.helpers import GoDjangoTestCase, DjangoVumiApiHelper
from go.billing.models import (
    Account, TagPool, MessageCost, Transaction, TransactionArchive,
    Statement, LineItem)
from go.billing.tests.helpers import (
    start_of_month, end_of_month, this_month, maybe_decimal,
    get_billing_account, mk_tagpool, mk_message_cost,
    mk_transaction, mk_transaction_archive,
    mk_statement, get_session_length_cost,
    get_message_credits, get_session_credits,
    get_storage_credits, get_session_length_credits, get_line_items)


class TestHelpers(GoDjangoTestCase):
    def setUp(self):
        self.vumi_helper = self.add_helper(DjangoVumiApiHelper())
        self.user_helper = self.vumi_helper.make_django_user()
        self.user = self.user_helper.get_django_user()
        self.account = Account.objects.get(user=self.user)

    def test_start_of_month(self):
        self.assertEqual(start_of_month(date(2015, 3, 23)), date(2015, 3, 1))
        self.assertEqual(start_of_month(date(2015, 4, 28)), date(2015, 4, 1))
        self.assertEqual(start_of_month(date(2015, 5, 31)), date(2015, 5, 1))

    def test_start_of_month_default(self):
        self.assertEqual(start_of_month(), start_of_month(date.today()))

    def test_end_of_month(self):
        self.assertEqual(end_of_month(date(2015, 3, 23)), date(2015, 3, 31))
        self.assertEqual(end_of_month(date(2015, 4, 28)), date(2015, 4, 30))
        self.assertEqual(end_of_month(date(2015, 5, 31)), date(2015, 5, 31))

    def test_end_of_month_default(self):
        self.assertEqual(end_of_month(), end_of_month(date.today()))

    def test_this_month(self):
        self.assertEqual(
            this_month(date(2015, 3, 23)),
            (date(2015, 3, 1), date(2015, 3, 31)))

        self.assertEqual(
            this_month(date(2015, 4, 28)),
            (date(2015, 4, 1), date(2015, 4, 30)))

        self.assertEqual(
            this_month(date(2015, 5, 31)),
            (date(2015, 5, 1), date(2015, 5, 31)))

    def test_this_month_today(self):
        self.assertEqual(this_month(), this_month(date.today()))

    def test_maybe_decimal_none(self):
        self.assertEqual(maybe_decimal(None), None)

    def test_maybe_decimal_float(self):
        self.assertEqual(maybe_decimal(23.23), Decimal('23.23'))

    def test_maybe_decimal_str(self):
        self.assertEqual(maybe_decimal('23.23'), Decimal('23.23'))

    def test_maybe_decimal_int(self):
        self.assertEqual(maybe_decimal(23), Decimal('23.0'))

    def test_maybe_decimal_decimal(self):
        self.assertEqual(maybe_decimal(Decimal('23.23')), Decimal('23.23'))

    def test_get_billing_account(self):
        self.assertEqual(get_billing_account(self.user), self.account)

    def test_mk_tagpool(self):
        pool = mk_tagpool('pool1')
        [found_pool] = TagPool.objects.filter(name='pool1')
        self.assertEqual(pool, found_pool)

    def test_mk_message_cost(self):
        pool = mk_tagpool('pool1')

        cost = mk_message_cost(
            tag_pool=pool,
            message_direction=MessageCost.DIRECTION_INBOUND,
            message_cost=0.1,
            storage_cost=0.2,
            session_cost=0.3,
            markup_percent=10.0)

        [found_cost] = MessageCost.objects.filter(
            tag_pool=pool,
            message_direction=MessageCost.DIRECTION_INBOUND,
            message_cost=Decimal('0.1'),
            storage_cost=Decimal('0.2'),
            session_cost=Decimal('0.3'),
            markup_percent=Decimal('10.0'))

        self.assertEqual(cost, found_cost)

    def test_mk_transaction(self):
        transaction = mk_transaction(
            account=self.account,
            transaction_type=Transaction.TRANSACTION_TYPE_MESSAGE,
            tag_pool_name='pool1',
            tag_name='tag1',
            provider='mtn',
            message_direction=MessageCost.DIRECTION_INBOUND,
            message_cost=0.1,
            storage_cost=0.2,
            session_cost=0.3,
            session_unit_cost=0.4,
            session_length_cost=0.4,
            markup_percent=10.0,
            credit_factor=11.0,
            credit_amount=28,
            session_length=23,
            created=date(2015, 3, 23),
            status=Transaction.STATUS_COMPLETED)

        [found_transaction] = Transaction.objects.filter(
            account_number=self.account.account_number,
            transaction_type=Transaction.TRANSACTION_TYPE_MESSAGE,
            provider='mtn',
            tag_pool_name='pool1',
            tag_name='tag1',
            message_direction=MessageCost.DIRECTION_INBOUND,
            message_cost=Decimal('0.1'),
            storage_cost=Decimal('0.2'),
            session_cost=Decimal('0.3'),
            session_unit_cost=Decimal('0.4'),
            session_length_cost=Decimal('0.4'),
            message_credits=get_message_credits(0.1, 10.0),
            storage_credits=get_storage_credits(0.2, 10.0),
            session_credits=get_session_credits(0.3, 10.0),
            session_length_credits=get_session_length_credits(0.4, 10.0),
            markup_percent=Decimal('10.0'),
            credit_factor=Decimal('11.0'),
            credit_amount=28,
            session_length=Decimal('23.0'),
            created=date(2015, 3, 23),
            status=Transaction.STATUS_COMPLETED)

        self.assertEqual(transaction, found_transaction)

    def test_mk_transaction_archive(self):
        archive = mk_transaction_archive(
            account=self.account,
            from_date=date(2015, 3, 21),
            to_date=date(2015, 3, 22),
            status=TransactionArchive.STATUS_ARCHIVE_COMPLETED)

        [found_archive] = TransactionArchive.objects.filter(
            account=self.account,
            from_date=date(2015, 3, 21),
            to_date=date(2015, 3, 22),
            status=TransactionArchive.STATUS_ARCHIVE_COMPLETED)

        self.assertEqual(archive, found_archive)

    def test_mk_statement(self):
        statement = mk_statement(
            account=self.account,
            title='Foo',
            statement_type=Statement.TYPE_MONTHLY,
            from_date=date(2015, 3, 23),
            to_date=date(2015, 4, 23),
            items=[{
                'billed_by': 'Pool 1',
                'channel_type': 'USSD',
                'channel': 'Tag 1.1',
                'description': 'Messages Received',
                'cost': Decimal('150.0'),
                'credits': Decimal('200.0'),
            }, {
                'billed_by': 'Pool 2',
                'channel_type': 'SMS',
                'channel': 'Tag 2.1',
                'description': 'Messages Received',
                'cost': Decimal('200.0'),
                'credits': None,
            }])

        [found_statement] = Statement.objects.filter(
            account=self.account,
            title='Foo',
            type=Statement.TYPE_MONTHLY,
            from_date=date(2015, 3, 23),
            to_date=date(2015, 4, 23))

        self.assertEqual(statement, found_statement)

        self.assertEqual(1, len(LineItem.objects.filter(
            statement=statement,
            billed_by='Pool 1',
            channel_type='USSD',
            channel='Tag 1.1',
            description='Messages Received',
            cost=Decimal('150.0'),
            credits=Decimal('200.0'))))

        self.assertEqual(1, len(LineItem.objects.filter(
            statement=statement,
            billed_by='Pool 2',
            channel_type='SMS',
            channel='Tag 2.1',
            description='Messages Received',
            cost=Decimal('200.0'),
            credits=None)))

    def test_get_session_length_cost(self):
        self.assertEqual(
            get_session_length_cost(1, 2, 3),
            MessageCost.calculate_session_length_cost(
                Decimal('1.0'),
                Decimal('2.0'),
                Decimal('3.0')))

    def test_get_message_credits(self):
        self.assertEqual(
            get_message_credits(0.1, 10.0),
            MessageCost.calculate_message_credit_cost(
                Decimal('0.1'),
                Decimal('10.0')))

    def test_get_message_credits_none_cost(self):
        self.assertEqual(get_message_credits(0.1, None), None)

    def test_get_message_credits_none_markup(self):
        self.assertEqual(get_message_credits(None, 10.0), None)

    def test_get_storage_credits(self):
        self.assertEqual(
            get_storage_credits(0.1, 10.0),
            MessageCost.calculate_storage_credit_cost(
                Decimal('0.1'),
                Decimal('10.0')))

    def test_get_storage_credits_none_cost(self):
        self.assertEqual(get_storage_credits(0.1, None), None)

    def test_get_storage_credits_none_markup(self):
        self.assertEqual(get_storage_credits(None, 10.0), None)

    def test_get_session_credits(self):
        self.assertEqual(
            get_session_credits(0.1, 10.0),
            MessageCost.calculate_session_credit_cost(
                Decimal('0.1'),
                Decimal('10.0')))

    def test_get_session_credits_none_cost(self):
        self.assertEqual(get_session_credits(0.1, None), None)

    def test_get_session_credits_none_markup(self):
        self.assertEqual(get_session_credits(None, 10.0), None)

    def test_get_session_length_credits(self):
        self.assertEqual(
            get_session_length_credits(0.1, 10.0),
            MessageCost.calculate_session_length_credit_cost(
                Decimal('0.1'),
                Decimal('10.0')))

    def test_get_session_length_credits_none_cost(self):
        self.assertEqual(get_session_length_credits(0.1, None), None)

    def test_get_session_length_credits_none_markup(self):
        self.assertEqual(get_session_length_credits(None, 10.0), None)

    def test_get_line_items(self):
        statement = mk_statement(
            account=self.account,
            items=[{
                'billed_by': 'Pool 1',
                'description': 'A',
                'credits': Decimal('23.23')
            }, {
                'billed_by': 'Pool 2',
                'description': 'B',
                'credits': Decimal('23.23')
            }, {
                'billed_by': 'Pool 3',
                'description': 'A',
                'credits': Decimal('3.3')
            }])

        self.assertEqual(list(get_line_items(statement)), [
            LineItem.objects.get(
                description='A',
                credits=Decimal('3.3')),
            LineItem.objects.get(
                description='A',
                credits=Decimal('23.23')),
            LineItem.objects.get(
                description='B',
                credits=Decimal('23.23')),
        ])
