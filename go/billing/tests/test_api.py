import json
import decimal

import pytest

from twisted.internet import defer

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


class TestUser(VumiTestCase):

    @pytest.mark.django_db
    @defer.inlineCallbacks
    def setUp(self):
        connection_string = app_settings.get_connection_string()
        connection_pool = DictRowConnectionPool(
            None, connection_string, min=app_settings.API_MIN_CONNECTIONS)

        self.connection_pool = yield connection_pool.start()
        root = api.Root(connection_pool)
        self.web = DummySite(root)

    @pytest.mark.django_db
    def tearDown(self):
        self.connection_pool.close()

    @skipif_unsupported_db
    @pytest.mark.django_db
    @defer.inlineCallbacks
    def runTest(self):
        # Create a new user
        content = {
            'email': "test@example.com",
            'first_name': "Test",
            'last_name': "User",
            'password': "password"
        }

        headers = {'content-type': 'application/json'}
        response = yield self.web.post(
            'users', args=None, content=content, headers=headers)

        self.assertEqual(response.responseCode, 200)
        new_user = json.loads(response.value(), cls=JSONDecoder)
        self.assertTrue('id' in new_user)

        # Fetch the new user
        url = 'users/%s' % (new_user.get('id'))
        response = yield self.web.get(url)
        self.assertEqual(response.responseCode, 200)
        user = json.loads(response.value(), cls=JSONDecoder)
        self.assertEqual(user.get('email'), new_user.get('email'))

        # Fetch a list of all users and make sure the new user is there
        response = yield self.web.get('users')
        self.assertEqual(response.responseCode, 200)
        user_list = json.loads(response.value(), cls=JSONDecoder)
        self.assertTrue(len(user_list) > 0)
        email_list = [u.get('email', None) for u in user_list]
        self.assertTrue("test@example.com" in email_list)


class TestAccount(VumiTestCase):

    @pytest.mark.django_db
    @defer.inlineCallbacks
    def setUp(self):
        connection_string = app_settings.get_connection_string()
        connection_pool = DictRowConnectionPool(
            None, connection_string, min=app_settings.API_MIN_CONNECTIONS)

        self.connection_pool = yield connection_pool.start()
        root = api.Root(connection_pool)
        self.web = DummySite(root)

    @pytest.mark.django_db
    def tearDown(self):
        self.connection_pool.close()

    @skipif_unsupported_db
    @pytest.mark.django_db
    @defer.inlineCallbacks
    def runTest(self):
        # Create a new user
        content = {
            'email': "test2@example.com",
            'first_name': "Test",
            'last_name': "User",
            'password': "password"
        }

        headers = {'content-type': 'application/json'}
        response = yield self.web.post(
            'users', args=None, content=content, headers=headers)

        self.assertEqual(response.responseCode, 200)
        user = json.loads(response.value(), cls=JSONDecoder)
        self.assertTrue('id' in user)

        # Create a new account
        content = {
            'email': "test2@example.com",
            'account_number': "12345",
            'description': "Test account"
        }

        headers = {'content-type': 'application/json'}
        response = yield self.web.post(
            'accounts', args=None, content=content, headers=headers)

        self.assertEqual(response.responseCode, 200)
        new_account = json.loads(response.value(), cls=JSONDecoder)
        self.assertEqual(new_account.get('account_number', None), "12345")

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
        url = 'accounts/%s' % (new_account.get('account_number'))
        response = yield self.web.get(url)
        self.assertEqual(response.responseCode, 200)
        account = json.loads(response.value(), cls=JSONDecoder)
        self.assertEqual(account.get('account_number'),
                         new_account.get('account_number'))
        self.assertTrue(account.get('credit_balance', 0) == 100)

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


class TestCost(VumiTestCase):

    @pytest.mark.django_db
    @defer.inlineCallbacks
    def setUp(self):
        connection_string = app_settings.get_connection_string()
        connection_pool = DictRowConnectionPool(
            None, connection_string, min=app_settings.API_MIN_CONNECTIONS)

        self.connection_pool = yield connection_pool.start()
        root = api.Root(connection_pool)
        self.web = DummySite(root)

    @pytest.mark.django_db
    def tearDown(self):
        self.connection_pool.close()

    @skipif_unsupported_db
    @pytest.mark.django_db
    @defer.inlineCallbacks
    def runTest(self):
        # Create a test user
        content = {
            'email': "test3@example.com",
            'first_name': "Test",
            'last_name': "User",
            'password': "password"
        }

        headers = {'content-type': 'application/json'}
        response = yield self.web.post(
            'users', args=None, content=content, headers=headers)

        self.assertEqual(response.responseCode, 200)
        user = json.loads(response.value(), cls=JSONDecoder)
        self.assertTrue('id' in user)

        # Create a test account
        content = {
            'email': "test3@example.com",
            'account_number': "67890",
            'description': "Test account"
        }

        headers = {'content-type': 'application/json'}
        response = yield self.web.post(
            'accounts', args=None, content=content, headers=headers)

        self.assertEqual(response.responseCode, 200)
        account = json.loads(response.value(), cls=JSONDecoder)

        # Create the message base cost
        content = {
            'tag_pool_name': "test_pool",
            'message_direction': "Outbound",
            'message_cost': 0.9,
            'markup_percent': 20.0,
        }

        headers = {'content-type': 'application/json'}
        response = yield self.web.post(
            'costs', args=None, content=content, headers=headers)

        self.assertEqual(response.responseCode, 200)
        base_cost = json.loads(response.value(), cls=JSONDecoder)
        self.assertTrue('credit_amount' in base_cost)
        message_cost = decimal.Decimal('0.9')
        markup_percent = decimal.Decimal('20.0')
        credit_amount = MessageCost.calculate_credit_cost(message_cost,
                                                          markup_percent)

        self.assertEqual(base_cost.get('credit_amount'), credit_amount)

        # Get the message cost
        args = {
            'tag_pool_name': "test_pool",
            'message_direction': "Outbound"
        }

        response = yield self.web.get('costs', args=args)
        self.assertEqual(response.responseCode, 200)
        message_cost = json.loads(response.value(), cls=JSONDecoder)
        self.assertTrue(len(message_cost) > 0)
        self.assertEqual(message_cost[0].get('credit_amount'), credit_amount)

        # Override the message cost for the account
        content = {
            'account_number': account.get('account_number'),
            'tag_pool_name': "test_pool",
            'message_direction': "Outbound",
            'message_cost': 0.5,
            'markup_percent': 10.0,
        }

        headers = {'content-type': 'application/json'}
        response = yield self.web.post(
            'costs', args=None, content=content, headers=headers)

        self.assertEqual(response.responseCode, 200)
        cost_override = json.loads(response.value(), cls=JSONDecoder)
        self.assertTrue('credit_amount' in base_cost)
        message_cost = decimal.Decimal('0.5')
        markup_percent = decimal.Decimal('10.0')
        credit_amount = MessageCost.calculate_credit_cost(message_cost,
                                                          markup_percent)

        self.assertEqual(cost_override.get('credit_amount'), credit_amount)

        # Get the message cost again
        args = {
            'account_number': account.get('account_number'),
            'tag_pool_name': "test_pool",
            'message_direction': "Outbound"
        }

        response = yield self.web.get('costs', args=args)
        self.assertEqual(response.responseCode, 200)
        message_cost = json.loads(response.value(), cls=JSONDecoder)
        self.assertTrue(len(message_cost) > 0)
        self.assertEqual(message_cost[0].get('credit_amount'), credit_amount)


class TestTransaction(VumiTestCase):

    @pytest.mark.django_db
    @defer.inlineCallbacks
    def setUp(self):
        connection_string = app_settings.get_connection_string()
        connection_pool = DictRowConnectionPool(
            None, connection_string, min=app_settings.API_MIN_CONNECTIONS)

        self.connection_pool = yield connection_pool.start()
        root = api.Root(connection_pool)
        self.web = DummySite(root)

    @pytest.mark.django_db
    def tearDown(self):
        self.connection_pool.close()

    @skipif_unsupported_db
    @pytest.mark.django_db
    @defer.inlineCallbacks
    def runTest(self):
        # Create a test user
        content = {
            'email': "test4@example.com",
            'first_name': "Test",
            'last_name': "User",
            'password': "password"
        }

        headers = {'content-type': 'application/json'}
        response = yield self.web.post(
            'users', args=None, content=content, headers=headers)

        self.assertEqual(response.responseCode, 200)
        user = json.loads(response.value(), cls=JSONDecoder)
        self.assertTrue('id' in user)

        # Create a test account
        content = {
            'email': "test4@example.com",
            'account_number': "11111",
            'description': "Test account"
        }

        headers = {'content-type': 'application/json'}
        response = yield self.web.post(
            'accounts', args=None, content=content, headers=headers)

        self.assertEqual(response.responseCode, 200)
        account = json.loads(response.value(), cls=JSONDecoder)

        # Set the message cost
        content = {
            'tag_pool_name': "test_pool2",
            'message_direction': "Inbound",
            'message_cost': 0.6,
            'markup_percent': 10.0,
        }

        headers = {'content-type': 'application/json'}
        response = yield self.web.post(
            'costs', args=None, content=content, headers=headers)

        self.assertEqual(response.responseCode, 200)
        cost = json.loads(response.value(), cls=JSONDecoder)
        message_cost = decimal.Decimal('0.6')
        markup_percent = decimal.Decimal('10.0')
        credit_amount = MessageCost.calculate_credit_cost(message_cost,
                                                          markup_percent)

        self.assertEqual(cost.get('credit_amount'), credit_amount)

        # Create a transaction
        content = {
            'account_number': "11111",
            'tag_pool_name': "test_pool2",
            'tag_name': "12345",
            'message_direction': "Inbound"
        }

        headers = {'content-type': 'application/json'}
        response = yield self.web.post(
            'transactions', args=None, content=content, headers=headers)

        self.assertEqual(response.responseCode, 200)

        # Make sure there was a transaction created
        args = {'account_number': account.get('account_number')}
        response = yield self.web.get('transactions', args=args)
        self.assertEqual(response.responseCode, 200)
        transaction_list = json.loads(response.value(), cls=JSONDecoder)
        self.assertTrue(len(transaction_list) > 0)
        found = False
        for transaction in transaction_list:
            if transaction.get('account_number', None) == '11111' \
                    and transaction.get('credit_amount', None) == \
                    -credit_amount \
                    and transaction.get('status', None) == 'Completed':
                found = True
                break
        self.assertTrue(found)

        # Get the account and make sure the credit balance was updated
        url = 'accounts/%s' % ("11111",)
        response = yield self.web.get(url)
        self.assertEqual(response.responseCode, 200)
        account = json.loads(response.value(), cls=JSONDecoder)
        self.assertTrue(account.get('credit_balance', 0) == -credit_amount)
