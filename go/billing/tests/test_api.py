import json
from decimal import Decimal

import mock
import pytest

from twisted.internet.defer import inlineCallbacks, returnValue

from vumi.tests.helpers import VumiTestCase

from go.billing import settings as app_settings
from go.billing import api
from go.billing.models import MessageCost
from go.billing.utils import DummySite, DictRowConnectionPool, JSONDecoder
from go.billing.tests.helpers import (
    get_message_credits, get_storage_credits, get_session_credits)

DB_SUPPORTED = False
try:
    app_settings.get_connection_string()
    DB_SUPPORTED = True
except ValueError:
    pass

skipif_unsupported_db = pytest.mark.skipif(
    "True" if not DB_SUPPORTED else "False",
    reason="Billing API requires PostGreSQL")


class ApiCallError(Exception):
    """Raised if a billing API call fails."""

    def __init__(self, response):
        super(ApiCallError, self).__init__(response.value())
        self.response = response


@skipif_unsupported_db
@pytest.mark.django_db
class BillingApiTestCase(VumiTestCase):

    @inlineCallbacks
    def setUp(self):
        connection_string = app_settings.get_connection_string()
        connection_pool = DictRowConnectionPool(
            None, connection_string, min=app_settings.API_MIN_CONNECTIONS)
        self.connection_pool = yield connection_pool.start()
        root = api.Root(connection_pool)
        self.web = DummySite(root)

    @inlineCallbacks
    def tearDown(self):
        for table in ('billing_lowcreditnotification', 'billing_transaction',
                      'billing_messagecost', 'billing_tagpool',
                      'billing_account'):
            yield self.connection_pool.runOperation(
                'DELETE FROM %s' % (table,))
        self.connection_pool.close()

    @inlineCallbacks
    def call_api(self, method, path, **kw):
        headers = {'content-type': 'application/json'}
        http_method = getattr(self.web, method)
        response = yield http_method(path, headers=headers, **kw)
        if response.responseCode != 200:
            raise ApiCallError(response)
        result = json.loads(response.value(), cls=JSONDecoder)
        returnValue(result)

    def create_api_user(self, email="test@example.com", first_name="Test",
                        last_name="User", password="password"):
        """
        Create a user by calling the billing API.
        """
        # TODO use django queryset
        content = {
            'email': email, 'first_name': first_name,
            'last_name': last_name, 'password': password,
        }
        return self.call_api('post', 'users', content=content)

    def create_api_account(self, email="test@example.com",
                           account_number="12345", description="Test account"):
        """
        Create an account by calling the billing API.
        """
        # TODO use django queryset
        content = {
            'email': email, 'account_number': account_number,
            'description': description,
        }
        return self.call_api('post', 'accounts', content=content)

    def get_api_account(self, account_number):
        """
        Retrieve an account by account number.
        """
        # TODO use django queryset
        return self.call_api('get', 'accounts/%s' % (account_number,))

    def get_api_account_list(self):
        """
        Retrieve a list of all accounts.
        """
        return self.call_api('get', 'accounts')

    def load_api_account_credits(self, account_number, credit_amount):
        """
        Load credits to an account via the API.
        """
        # TODO use django queryset
        content = {
            'credit_amount': credit_amount,
        }
        return self.call_api('post', 'accounts/%s/credits' % (account_number,),
                             content=content)

    def create_api_cost(self, account_number=None, tag_pool_name=None,
                        message_direction='', message_cost=0.0,
                        storage_cost=0.0, session_cost=0.0,
                        markup_percent=0.0):
        """
        Create a message cost record via the billing API.
        """
        # TODO use django queryset
        content = {
            'account_number': account_number,
            'tag_pool_name': tag_pool_name,
            'message_direction': message_direction,
            'message_cost': message_cost,
            'storage_cost': storage_cost,
            'session_cost': session_cost,
            'markup_percent': markup_percent,
        }
        return self.call_api('post', 'costs', content=content)

    def create_api_transaction(self, account_number, message_id, tag_pool_name,
                               tag_name, message_direction, session_created):
        """
        Create a transaction record via the billing API.
        """
        # TODO use django queryset
        content = {
            'account_number': account_number,
            'message_id': message_id,
            'tag_pool_name': tag_pool_name,
            'tag_name': tag_name,
            'message_direction': message_direction,
            'session_created': session_created,
        }
        return self.call_api('post', 'transactions', content=content)

    def get_api_transaction_list(self, account_number):
        """
        Retrieve the list of transactions for a given account number.
        """
        # TODO use django queryset
        args = {
            'account_number': account_number,
        }
        return self.call_api('get', 'transactions', args=args)


class TestTransaction(BillingApiTestCase):

    def setUp(self):
        self.patch(app_settings, 'LOW_CREDIT_NOTIFICATION_PERCENTAGES',
                   [70, 90, 80])
        return BillingApiTestCase.setUp(self)

    def test_check_all_low_credit_thresholds(self):
        """
        Tests various combinations of parameters for
        TransactionResource.check_all_low_credit_thresholds.
        """
        resource = api.TransactionResource(None)
        crossed = resource.check_all_low_credit_thresholds
        # Argument order: credit_balance, credit_amount, last_topup_balance
        # Thresholds are: 70%, 80% and 90%
        # simple notification level crossings
        self.assertEqual(crossed(90, 1, 100), Decimal('0.9'))
        self.assertEqual(crossed(80, 1, 100), Decimal('0.8'))
        self.assertEqual(crossed(70, 1, 100), Decimal('0.7'))
        # simple non-crossings
        self.assertEqual(crossed(60, 1, 100), None)
        self.assertEqual(crossed(91, 1, 100), None)
        self.assertEqual(crossed(89, 1, 100), None)
        # crossing multiple percentages in one go
        self.assertEqual(crossed(89, 2, 100), Decimal('0.9'))
        self.assertEqual(crossed(65, 10, 100), Decimal('0.7'))
        # non-crossings around 0 and 100
        self.assertEqual(crossed(0, 0, 100), None)
        self.assertEqual(crossed(100, 0, 100), None)
        self.assertEqual(crossed(-5, 1, 100), None)
        self.assertEqual(crossed(105, 1, 100), None)

    @inlineCallbacks
    def test_low_credit_threshold_notifications(self):
        # patch settings and task
        mock_task_delay = mock.MagicMock()
        self.patch(app_settings, 'ENABLE_LOW_CREDIT_NOTIFICATION', True)
        self.patch(
            api.create_low_credit_notification, 'delay', mock_task_delay)
        # Create account
        yield self.create_api_user(email="test4@example.com")
        account = yield self.create_api_account(
            email="test4@example.com", account_number="11112")

        # Load credits
        yield self.load_api_account_credits(
            account['account_number'], 10)

        # Set the message cost
        yield self.create_api_cost(
            tag_pool_name="test_pool2",
            message_direction="Inbound",
            message_cost=0.1, session_cost=0.1,
            markup_percent=0.1)

        # Create a transaction
        yield self.create_api_transaction(
            account_number=account['account_number'],
            message_id='msg-id-1',
            tag_pool_name="test_pool2",
            tag_name="12345",
            message_direction="Inbound",
            session_created=False)

        # It should create the first notification
        account = yield self.get_api_account(account["account_number"])
        mock_task_delay.assert_called_once_with(
            account['account_number'], Decimal('0.9'),
            account['credit_balance'])
        mock_task_delay.reset_mock()

        # Create another transaction
        yield self.create_api_transaction(
            account_number=account['account_number'],
            message_id='msg-id-2',
            tag_pool_name="test_pool2",
            tag_name="12345",
            message_direction="Inbound",
            session_created=False)

        # It should create the second notification
        account = yield self.get_api_account(account["account_number"])
        mock_task_delay.assert_called_once_with(
            account['account_number'], Decimal('0.8'),
            account['credit_balance'])
        mock_task_delay.reset_mock()

        # Create a third transaction
        yield self.create_api_transaction(
            account_number=account['account_number'],
            message_id='msg-id-2',
            tag_pool_name="test_pool2",
            tag_name="12345",
            message_direction="Inbound",
            session_created=False)

        # It should create the third notification
        account = yield self.get_api_account(account["account_number"])
        mock_task_delay.assert_called_once_with(
            account['account_number'], Decimal('0.7'),
            account['credit_balance'])
        mock_task_delay.reset_mock()

        # Create a fourth transaction
        yield self.create_api_transaction(
            account_number=account['account_number'],
            message_id='msg-id-2',
            tag_pool_name="test_pool2",
            tag_name="12345",
            message_direction="Inbound",
            session_created=False)

        # It should not create any more notifications
        self.assertFalse(mock_task_delay.called)

    @inlineCallbacks
    def test_low_credit_notification_zero_last_topup_value(self):
        # patch settings and task
        mock_task_delay = mock.MagicMock()
        self.patch(app_settings, 'ENABLE_LOW_CREDIT_NOTIFICATION', True)
        self.patch(
            api.create_low_credit_notification, 'delay', mock_task_delay)

        # Create account
        yield self.create_api_user(email="test5@example.com")
        account = yield self.create_api_account(
            email="test5@example.com", account_number="11113")

        self.assertEqual(account['last_topup_balance'], Decimal('0.0'))

        # Set the message cost
        yield self.create_api_cost(
            tag_pool_name="test_pool2",
            message_direction="Inbound",
            message_cost=0.1, session_cost=0.1,
            markup_percent=0.1)

        # Create a transaction
        yield self.create_api_transaction(
            account_number=account['account_number'],
            message_id='msg-id-1',
            tag_pool_name="test_pool2",
            tag_name="12345",
            message_direction="Inbound",
            session_created=False)

        self.assertFalse(mock_task_delay.called)

    @inlineCallbacks
    def test_transaction(self):
        yield self.create_api_user(email="test6@example.com")
        account = yield self.create_api_account(email="test6@example.com",
                                                account_number="11111")

        # Set the message cost
        yield self.create_api_cost(
            tag_pool_name="test_pool2",
            message_direction="Inbound",
            message_cost=0.6,
            storage_cost=0.5,
            session_cost=0.3,
            markup_percent=10.0)

        credit_amount = MessageCost.calculate_credit_cost(
            Decimal('0.6'),
            Decimal('0.5'),
            Decimal('10.0'),
            Decimal('0.3'),
            session_created=False)

        credit_amount_for_session = MessageCost.calculate_credit_cost(
            Decimal('0.6'),
            Decimal('0.5'),
            Decimal('10.0'),
            Decimal('0.3'),
            session_created=True)

        # Create a transaction
        yield self.create_api_transaction(
            account_number=account['account_number'],
            message_id='msg-id-1',
            tag_pool_name="test_pool2",
            tag_name="12345",
            message_direction="Inbound",
            session_created=False)

        # Make sure there was a transaction created
        [transaction] = yield self.get_api_transaction_list(
            account["account_number"])
        del (transaction['id'], transaction['created'],
             transaction['last_modified'])
        self.assertEqual(transaction, {
            u'account_number': account['account_number'],
            u'message_id': 'msg-id-1',
            u'credit_amount': -credit_amount,
            u'credit_factor': Decimal('10.000000'),
            u'markup_percent': Decimal('10.000000'),
            u'message_cost': Decimal('0.6'),
            u'storage_cost': Decimal('0.5'),
            u'message_direction': u'Inbound',
            u'session_cost': Decimal('0.3'),
            u'session_created': False,
            u'message_credits': get_message_credits(0.6, 10.0),
            u'storage_credits': get_storage_credits(0.5, 10.0),
            u'session_credits': get_session_credits(0.3, 10.0),
            u'status': u'Completed',
            u'tag_name': u'12345',
            u'tag_pool_name': u'test_pool2'
        })

        # Get the account and make sure the credit balance was updated
        account = yield self.get_api_account(account["account_number"])
        self.assertEqual(account['credit_balance'], -credit_amount)

        # Create a transaction (with session_created=True)
        yield self.create_api_transaction(
            account_number=account['account_number'],
            message_id='msg-id-2',
            tag_pool_name="test_pool2",
            tag_name="12345",
            message_direction="Inbound",
            session_created=True)

        # Make sure there was a transaction created (with session_created=True)
        [transaction, _] = yield self.get_api_transaction_list(
            account["account_number"])
        del (transaction['id'], transaction['created'],
             transaction['last_modified'])
        self.assertEqual(transaction, {
            u'account_number': account['account_number'],
            u'message_id': 'msg-id-2',
            u'credit_amount': -credit_amount_for_session,
            u'credit_factor': Decimal('10.000000'),
            u'markup_percent': Decimal('10.000000'),
            u'message_cost': Decimal('0.6'),
            u'storage_cost': Decimal('0.5'),
            u'message_direction': u'Inbound',
            u'session_cost': Decimal('0.3'),
            u'session_created': True,
            u'message_credits': get_message_credits(0.6, 10.0),
            u'storage_credits': get_storage_credits(0.5, 10.0),
            u'session_credits': get_session_credits(0.3, 10.0),
            u'status': u'Completed',
            u'tag_name': u'12345',
            u'tag_pool_name': u'test_pool2'
        })

        # Get the account and make sure the credit balance was updated
        account = yield self.get_api_account(account["account_number"])
        self.assertEqual(account['credit_balance'],
                         -(credit_amount + credit_amount_for_session))

        # Test override of cost by cost for specific account
        yield self.create_api_cost(
            account_number=account["account_number"],
            tag_pool_name="test_pool2",
            message_direction="Inbound",
            message_cost=9.0,
            storage_cost=8.0,
            session_cost=7.0,
            markup_percent=11.0)

        transaction = yield self.create_api_transaction(
            account_number=account['account_number'],
            message_id='msg-id-3',
            tag_pool_name="test_pool2",
            tag_name="12345",
            message_direction="Inbound",
            session_created=False)

        credit_amount = MessageCost.calculate_credit_cost(
            Decimal('9.0'),
            Decimal('8.0'),
            Decimal('11.0'),
            Decimal('7.0'),
            session_created=False)

        del (transaction['id'], transaction['created'],
             transaction['last_modified'])
        self.assertEqual(transaction, {
            u'account_number': account['account_number'],
            u'message_id': 'msg-id-3',
            u'credit_amount': -credit_amount,
            u'credit_factor': Decimal('10.0'),
            u'markup_percent': Decimal('11.0'),
            u'message_cost': Decimal('9.0'),
            u'storage_cost': Decimal('8.0'),
            u'message_direction': u'Inbound',
            u'session_cost': Decimal('7.0'),
            u'session_created': False,
            u'message_credits': get_message_credits(9.0, 11.0),
            u'storage_credits': get_storage_credits(8.0, 11.0),
            u'session_credits': get_session_credits(7.0, 11.0),
            u'status': u'Completed',
            u'tag_name': u'12345',
            u'tag_pool_name': u'test_pool2',
        })

        # Test fallback to default cost
        yield self.create_api_cost(
            message_direction="Outbound",
            message_cost=0.1,
            storage_cost=0.3,
            session_cost=0.2,
            markup_percent=12.0)

        yield self.create_api_user(email="test7@example.com")
        account = yield self.create_api_account(
            email="test7@example.com", account_number="arbitrary-user")

        transaction = yield self.create_api_transaction(
            account_number="arbitrary-user",
            message_id='msg-id-4',
            tag_pool_name="some-random-pool",
            tag_name="erk",
            message_direction="Outbound",
            session_created=False)

        credit_amount = MessageCost.calculate_credit_cost(
            Decimal('0.1'),
            Decimal('0.3'),
            Decimal('12.0'),
            Decimal('0.2'),
            session_created=False)

        del (transaction['id'], transaction['created'],
             transaction['last_modified'])
        self.assertEqual(transaction, {
            u'account_number': 'arbitrary-user',
            u'message_id': 'msg-id-4',
            u'credit_amount': -credit_amount,
            u'credit_factor': Decimal('10.0'),
            u'markup_percent': Decimal('12.0'),
            u'message_cost': Decimal('0.1'),
            u'storage_cost': Decimal('0.3'),
            u'message_direction': u'Outbound',
            u'session_cost': Decimal('0.2'),
            u'session_created': False,
            u'message_credits': get_message_credits(0.1, 12.0),
            u'storage_credits': get_storage_credits(0.3, 12.0),
            u'session_credits': get_session_credits(0.2, 12.0),
            u'status': u'Completed',
            u'tag_name': u'erk',
            u'tag_pool_name': u'some-random-pool',
        })

        # Test that message direction is correctly checked for
        # in the fallback case.
        try:
            yield self.create_api_transaction(
                account_number="arbitrary-user",
                message_id='msg-id-4',
                tag_pool_name="some-random-pool",
                tag_name="erk",
                message_direction="Inbound",
                session_created=False)
        except ApiCallError as e:
            self.assertEqual(e.response.responseCode, 500)
            self.assertEqual(
                e.message,
                "Unable to determine Inbound message cost for account"
                " arbitrary-user and tag pool some-random-pool")
        else:
            self.fail("Expected transaction creation to fail.")

        [failure] = self.flushLoggedErrors('go.billing.utils.BillingError')
        self.assertEqual(
            failure.value.args,
            ("Unable to determine Inbound message cost for account"
             " arbitrary-user and tag pool some-random-pool",))

        # Test that transactions for unknown accounts raised a BillingError
        try:
            yield self.create_api_transaction(
                account_number="unknown-account",
                message_id='msg-id-5',
                tag_pool_name="some-random-pool",
                tag_name="erk",
                message_direction="Outbound",
                session_created=False)
        except ApiCallError as e:
            self.assertEqual(e.response.responseCode, 500)
            self.assertEqual(
                e.message,
                "Unable to find billing account unknown-account while"
                " checking credit balance. Message was Outbound to/from"
                " tag pool some-random-pool.")
        else:
            self.fail("Expected transaction creation to fail.")

        [failure] = self.flushLoggedErrors('go.billing.utils.BillingError')
        self.assertEqual(
            failure.value.args,
            ("Unable to find billing account unknown-account while"
             " checking credit balance. Message was Outbound to/from"
             " tag pool some-random-pool.",))
