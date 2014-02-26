import json
import decimal

import pytest

from twisted.internet.defer import inlineCallbacks, returnValue

from vumi.tests.helpers import VumiTestCase

from go.billing import settings as app_settings
from go.billing import api
from go.billing.models import MessageCost
from go.billing.utils import DummySite, DictRowConnectionPool, JSONDecoder


DB_SUPPORTED = False
try:
    app_settings.get_connection_string()
    DB_SUPPORTED = True
except ValueError:
    pass

skipif_unsupported_db = pytest.mark.skipif(
    "True" if not DB_SUPPORTED else "False",
    reason="Billing API requires PostGreSQL")


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

    def tearDown(self):
        self.connection_pool.close()

    @inlineCallbacks
    def call_api(self, method, path, **kw):
        headers = {'content-type': 'application/json'}
        http_method = getattr(self.web, method)
        response = yield http_method(
            path, args=None, headers=headers, **kw)
        self.assertEqual(response.responseCode, 200)
        result = json.loads(response.value(), cls=JSONDecoder)
        returnValue(result)

    def create_api_user(self, email="test@example.com", first_name="Test",
                        last_name="User", password="password"):
        """
        Create a user by calling the billing API.
        """
        content = {
            'email': email, 'first_name': first_name,
            'last_name': last_name, 'password': password,
        }
        return self.call_api('post', 'users', content=content)

    def get_api_user(self, user_id):
        """
        Retrieve a user by id.
        """
        return self.call_api('get', 'users/%s' % (user_id,))

    def get_api_user_list(self):
        """
        Retrieve a list of all users.
        """
        return self.call_api('get', 'users')

    def create_api_account(self, email="test@example.com",
                           account_number="12345", description="Test account"):
        """
        Create an account by calling the billing API.
        """
        content = {
            'email': email, 'account_number': account_number,
            'description': description,
        }
        return self.call_api('post', 'accounts', content=content)

    def get_api_account(self, account_number):
        """
        Retrieve an account by account number.
        """
        return self.call_api('get', 'accounts/%s' % (account_number,))

# TODO: factor out cost setup method


class TestUser(BillingApiTestCase):

    @inlineCallbacks
    def test_user(self):
        # test creating the user
        new_user = yield self.create_api_user()
        user_id = new_user['id']
        self.assertTrue(user_id)
        self.assertEqual(new_user, {
            u'id': user_id,
            u'email': u'test@example.com',
            u'first_name': u'Test',
            u'last_name': u'User'
        })

        # test retrieving the user
        user = yield self.get_api_user(new_user['id'])
        self.assertEqual(user, new_user)

        # test retrieving all users
        user_list = yield self.get_api_user_list()
        self.assertEqual(user_list, [new_user])


class TestAccount(BillingApiTestCase):

    @inlineCallbacks
    def test_account(self):
        yield self.create_api_user(email="test2@example.com")
        new_account = yield self.create_api_account(email="test2@example.com")
        self.assertEqual(new_account, {
            "account_number": "12345",
            "alert_credit_balance": decimal.Decimal('0.0'),
            "alert_threshold": decimal.Decimal('0.0'),
            "credit_balance": decimal.Decimal('0.0'),
            "description": "Test account",
            "email": "test2@example.com",
        })

        # Load credits into the new account
        content = {
            'credit_amount': 100
        }

        headers = {'content-type': 'application/json'}
        url = 'accounts/%s/credits' % (new_account.get('account_number'),)
        response = yield self.web.post(url, args=None, content=content,
                                       headers=headers)

        self.assertEqual(response.responseCode, 200)

        # Fetch the new account and make sure the credit balance is correct
        account = yield self.get_api_account(new_account["account_number"])
        self.assertEqual(account, {
            "account_number": "12345",
            "alert_credit_balance": decimal.Decimal('0.0'),
            "alert_threshold": decimal.Decimal('0.0'),
            "credit_balance": decimal.Decimal('100.0'),
            "description": "Test account",
            "email": "test2@example.com",
        })

        # Make sure there was a transaction created for the credit load
        args = {'account_number': account.get('account_number')}
        response = yield self.web.get('transactions', args=args)
        self.assertEqual(response.responseCode, 200)
        transaction_list = json.loads(response.value(), cls=JSONDecoder)
        self.assertTrue(len(transaction_list) > 0)
        found = False
        for transaction in transaction_list:
            if transaction.get('account_number', None) == '12345' \
                    and transaction.get('credit_amount', None) == 100 \
                    and transaction.get('status', None) == 'Completed':
                found = True
                break
        self.assertTrue(found)


class TestCost(BillingApiTestCase):

    @inlineCallbacks
    def test_cost(self):
        yield self.create_api_user(email="test3@example.com")
        account = yield self.create_api_account(email="test3@example.com",
                                                account_number="67890")

        # Create the message base cost
        content = {
            'tag_pool_name': "test_pool",
            'message_direction': "Outbound",
            'message_cost': 0.9,
            'session_cost': 0.7,
            'markup_percent': 20.0,
        }

        headers = {'content-type': 'application/json'}
        response = yield self.web.post(
            'costs', args=None, content=content, headers=headers)

        self.assertEqual(response.responseCode, 200)
        base_cost = json.loads(response.value(), cls=JSONDecoder)
        self.assertEqual(base_cost, {
            u'account_number': None,
            u'markup_percent': decimal.Decimal('20.000000'),
            u'message_cost': decimal.Decimal('0.900000'),
            u'message_direction': u'Outbound',
            u'session_cost': decimal.Decimal('0.700000'),
            u'tag_pool_name': u'test_pool',
        })

        # Get the message cost
        args = {
            'tag_pool_name': "test_pool",
            'message_direction': "Outbound"
        }

        response = yield self.web.get('costs', args=args)
        self.assertEqual(response.responseCode, 200)
        [message_cost] = json.loads(response.value(), cls=JSONDecoder)
        self.assertEqual(message_cost, {
            u'account_number': None,
            u'markup_percent': decimal.Decimal('20.000000'),
            u'message_cost': decimal.Decimal('0.900000'),
            u'message_direction': u'Outbound',
            u'session_cost': decimal.Decimal('0.700000'),
            u'tag_pool_name': u'test_pool'
        })

        # Override the message cost for the account
        content = {
            'account_number': account['account_number'],
            'tag_pool_name': "test_pool",
            'message_direction': "Outbound",
            'message_cost': 0.5,
            'session_cost': 0.3,
            'markup_percent': 10.0,
        }

        headers = {'content-type': 'application/json'}
        response = yield self.web.post(
            'costs', args=None, content=content, headers=headers)
        self.assertEqual(response.responseCode, 200)
        cost_override = json.loads(response.value(), cls=JSONDecoder)
        self.assertEqual(cost_override, {
            u'account_number': account['account_number'],
            u'markup_percent': decimal.Decimal('10.000000'),
            u'message_cost': decimal.Decimal('0.500000'),
            u'message_direction': u'Outbound',
            u'session_cost': decimal.Decimal('0.300000'),
            u'tag_pool_name': u'test_pool',
        })

        # Get the message cost again
        args = {
            'account_number': account.get('account_number'),
            'tag_pool_name': "test_pool",
            'message_direction': "Outbound"
        }

        response = yield self.web.get('costs', args=args)
        self.assertEqual(response.responseCode, 200)
        [message_cost] = json.loads(response.value(), cls=JSONDecoder)
        self.assertEqual(message_cost, {
            u'account_number': account['account_number'],
            u'markup_percent': decimal.Decimal('10.000000'),
            u'message_cost': decimal.Decimal('0.500000'),
            u'message_direction': u'Outbound',
            u'session_cost': decimal.Decimal('0.300000'),
            u'tag_pool_name': u'test_pool'
        })


class TestTransaction(BillingApiTestCase):

    @inlineCallbacks
    def test_transaction(self):
        yield self.create_api_user(email="test4@example.com")
        account = yield self.create_api_account(email="test4@example.com",
                                                account_number="11111")

        # Set the message cost
        content = {
            'tag_pool_name': "test_pool2",
            'message_direction': "Inbound",
            'message_cost': 0.6,
            'session_cost': 0.3,
            'markup_percent': 10.0,
        }

        headers = {'content-type': 'application/json'}
        response = yield self.web.post(
            'costs', args=None, content=content, headers=headers)

        self.assertEqual(response.responseCode, 200)
        credit_amount = MessageCost.calculate_credit_cost(
            decimal.Decimal('0.6'), decimal.Decimal('10.0'),
            decimal.Decimal('0.3'), session_created=False)
        credit_amount_for_session = MessageCost.calculate_credit_cost(
            decimal.Decimal('0.6'), decimal.Decimal('10.0'),
            decimal.Decimal('0.3'), session_created=True)

        # Create a transaction
        content = {
            'account_number': account['account_number'],
            'message_id': 'msg-id-1',
            'tag_pool_name': "test_pool2",
            'tag_name': "12345",
            'message_direction': "Inbound",
            'session_created': False,
        }

        headers = {'content-type': 'application/json'}
        response = yield self.web.post(
            'transactions', args=None, content=content, headers=headers)

        self.assertEqual(response.responseCode, 200)

        # Make sure there was a transaction created
        args = {'account_number': account['account_number']}
        response = yield self.web.get('transactions', args=args)
        self.assertEqual(response.responseCode, 200)
        [transaction] = json.loads(response.value(), cls=JSONDecoder)
        del (transaction['id'], transaction['created'],
             transaction['last_modified'])
        self.assertEqual(transaction, {
            u'account_number': account['account_number'],
            u'message_id': 'msg-id-1',
            u'credit_amount': -credit_amount,
            u'credit_factor': decimal.Decimal('10.000000'),
            u'markup_percent': decimal.Decimal('10.000000'),
            u'message_cost': decimal.Decimal('0.6'),
            u'message_direction': u'Inbound',
            u'session_cost': decimal.Decimal('0.3'),
            u'session_created': False,
            u'status': u'Completed',
            u'tag_name': u'12345',
            u'tag_pool_name': u'test_pool2'
        })

        # Get the account and make sure the credit balance was updated
        account = yield self.get_api_account(account["account_number"])
        self.assertEqual(account['credit_balance'], -credit_amount)

        # Create a transaction (with session_created=True)
        content = {
            'account_number': account['account_number'],
            'message_id': 'msg-id-2',
            'tag_pool_name': "test_pool2",
            'tag_name': "12345",
            'message_direction': "Inbound",
            'session_created': True,
        }

        headers = {'content-type': 'application/json'}
        response = yield self.web.post(
            'transactions', args=None, content=content, headers=headers)

        self.assertEqual(response.responseCode, 200)

        # Make sure there was a transaction created (with session_created=True)
        args = {'account_number': account['account_number']}
        response = yield self.web.get('transactions', args=args)
        self.assertEqual(response.responseCode, 200)
        [transaction, _] = json.loads(response.value(), cls=JSONDecoder)
        del (transaction['id'], transaction['created'],
             transaction['last_modified'])
        self.assertEqual(transaction, {
            u'account_number': account['account_number'],
            u'message_id': 'msg-id-2',
            u'credit_amount': -credit_amount_for_session,
            u'credit_factor': decimal.Decimal('10.000000'),
            u'markup_percent': decimal.Decimal('10.000000'),
            u'message_cost': decimal.Decimal('0.6'),
            u'message_direction': u'Inbound',
            u'session_cost': decimal.Decimal('0.3'),
            u'session_created': True,
            u'status': u'Completed',
            u'tag_name': u'12345',
            u'tag_pool_name': u'test_pool2'
        })

        # Get the account and make sure the credit balance was updated
        account = yield self.get_api_account(account["account_number"])
        self.assertEqual(account['credit_balance'],
                         -(credit_amount + credit_amount_for_session))
