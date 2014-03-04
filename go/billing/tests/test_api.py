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
        for table in ('billing_transaction', 'billing_messagecost',
                      'billing_tagpool', 'billing_account'):
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

    def get_api_account_list(self):
        """
        Retrieve a list of all accounts.
        """
        return self.call_api('get', 'accounts')

    def load_api_account_credits(self, account_number, credit_amount):
        """
        Load credits to an account via the API.
        """
        content = {
            'credit_amount': credit_amount,
        }
        return self.call_api('post', 'accounts/%s/credits' % (account_number,),
                             content=content)

    def create_api_cost(self, account_number=None, tag_pool_name=None,
                        message_direction='', message_cost=0.0,
                        session_cost=0.0, markup_percent=0.0):
        """
        Create a message cost record via the billing API.
        """
        content = {
            'account_number': account_number,
            'tag_pool_name': tag_pool_name,
            'message_direction': message_direction,
            'message_cost': message_cost,
            'session_cost': session_cost,
            'markup_percent': markup_percent,
        }
        return self.call_api('post', 'costs', content=content)

    def get_api_costs(self, account_number=None, tag_pool_name=None,
                     message_direction=''):
        """
        Retrieve message costs by some combination of account number,
        tag pool name and message direction.
        """
        args = {
            'account_number': account_number,
            'tag_pool_name': tag_pool_name,
            'message_direction': message_direction,
        }
        return self.call_api('get', 'costs', args=args)

    def create_api_transaction(self, account_number, message_id, tag_pool_name,
                               tag_name, message_direction, session_created):
        """
        Create a transaction record via the billing API.
        """
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
        args = {
            'account_number': account_number,
        }
        return self.call_api('get', 'transactions', args=args)


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
        yield self.load_api_account_credits(
            new_account['account_number'], 100)

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
        [transaction] = yield self.get_api_transaction_list(
            account['account_number'])
        self.assertEqual(transaction['account_number'], '12345')
        self.assertEqual(transaction['credit_amount'], 100)
        self.assertEqual(transaction['status'], 'Completed')

        # Test listing all accounts
        [my_account] = yield self.get_api_account_list()
        self.assertEqual(my_account, account)


class TestCost(BillingApiTestCase):

    @inlineCallbacks
    def test_cost(self):
        yield self.create_api_user(email="test3@example.com")
        account = yield self.create_api_account(email="test3@example.com",
                                                account_number="67890")

        # Create the message base cost
        base_cost = yield self.create_api_cost(
            tag_pool_name="test_pool",
            message_direction="Outbound",
            message_cost=0.9, session_cost=0.7,
            markup_percent=20.0)
        self.assertEqual(base_cost, {
            u'account_number': None,
            u'markup_percent': decimal.Decimal('20.000000'),
            u'message_cost': decimal.Decimal('0.900000'),
            u'message_direction': u'Outbound',
            u'session_cost': decimal.Decimal('0.700000'),
            u'tag_pool_name': u'test_pool',
        })

        # Get the message cost
        [message_cost] = yield self.get_api_costs(
            tag_pool_name="test_pool",
            message_direction="Outbound")
        self.assertEqual(message_cost, {
            u'account_number': None,
            u'markup_percent': decimal.Decimal('20.000000'),
            u'message_cost': decimal.Decimal('0.900000'),
            u'message_direction': u'Outbound',
            u'session_cost': decimal.Decimal('0.700000'),
            u'tag_pool_name': u'test_pool'
        })

        # Override the message cost for the account
        cost_override = yield self.create_api_cost(
            account_number=account['account_number'],
            tag_pool_name="test_pool",
            message_direction="Outbound",
            message_cost=0.5, session_cost=0.3,
            markup_percent=10.0)
        self.assertEqual(cost_override, {
            u'account_number': account['account_number'],
            u'markup_percent': decimal.Decimal('10.000000'),
            u'message_cost': decimal.Decimal('0.500000'),
            u'message_direction': u'Outbound',
            u'session_cost': decimal.Decimal('0.300000'),
            u'tag_pool_name': u'test_pool',
        })

        # Get the message cost again
        [message_cost] = yield self.get_api_costs(
            account_number=account.get('account_number'),
            tag_pool_name="test_pool",
            message_direction="Outbound")
        self.assertEqual(message_cost, {
            u'account_number': account['account_number'],
            u'markup_percent': decimal.Decimal('10.000000'),
            u'message_cost': decimal.Decimal('0.500000'),
            u'message_direction': u'Outbound',
            u'session_cost': decimal.Decimal('0.300000'),
            u'tag_pool_name': u'test_pool'
        })

        # Test that setting a message cost with an account number
        # but no tag pool fails.
        try:
            yield self.create_api_cost(
                account_number=account['account_number'],
                tag_pool_name=None,
                message_direction="Outbound",
                message_cost=0.5, session_cost=0.3,
                markup_percent=10.0)
        except ApiCallError, e:
            self.assertEqual(e.response.responseCode, 400)
            self.assertEqual(e.message, "")
        else:
            self.fail("Expected cost creation to fail.")

        # create a message cost with no account or tag pool
        fallback_cost = yield self.create_api_cost(
            account_number=None,
            tag_pool_name=None,
            message_direction="Outbound",
            message_cost=0.1, session_cost=0.1,
            markup_percent=10.0)
        self.assertEqual(fallback_cost, {
            u'account_number': None,
            u'markup_percent': decimal.Decimal('10.0'),
            u'message_cost': decimal.Decimal('0.1'),
            u'message_direction': u'Outbound',
            u'session_cost': decimal.Decimal('0.1'),
            u'tag_pool_name': None,
        })

        # Test that we retrieve all the message costs
        all_costs = yield self.get_api_costs()
        self.assertEqual(
            all_costs, [cost_override, base_cost, fallback_cost])


class TestTransaction(BillingApiTestCase):

    @inlineCallbacks
    def test_transaction(self):
        yield self.create_api_user(email="test4@example.com")
        account = yield self.create_api_account(email="test4@example.com",
                                                account_number="11111")

        # Set the message cost
        yield self.create_api_cost(
            tag_pool_name="test_pool2",
            message_direction="Inbound",
            message_cost=0.6, session_cost=0.3,
            markup_percent=10.0)

        credit_amount = MessageCost.calculate_credit_cost(
            decimal.Decimal('0.6'), decimal.Decimal('10.0'),
            decimal.Decimal('0.3'), session_created=False)

        credit_amount_for_session = MessageCost.calculate_credit_cost(
            decimal.Decimal('0.6'), decimal.Decimal('10.0'),
            decimal.Decimal('0.3'), session_created=True)

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

        # Test override of cost by cost for specific account
        yield self.create_api_cost(
            account_number=account["account_number"],
            tag_pool_name="test_pool2",
            message_direction="Inbound",
            message_cost=9.0, session_cost=7.0,
            markup_percent=11.0)

        transaction = yield self.create_api_transaction(
            account_number=account['account_number'],
            message_id='msg-id-3',
            tag_pool_name="test_pool2",
            tag_name="12345",
            message_direction="Inbound",
            session_created=False)

        credit_amount = MessageCost.calculate_credit_cost(
            decimal.Decimal('9.0'), decimal.Decimal('11.0'),
            decimal.Decimal('7.0'), session_created=False)

        del (transaction['id'], transaction['created'],
             transaction['last_modified'])
        self.assertEqual(transaction, {
            u'account_number': account['account_number'],
            u'message_id': 'msg-id-3',
            u'credit_amount': -credit_amount,
            u'credit_factor': decimal.Decimal('10.0'),
            u'markup_percent': decimal.Decimal('11.0'),
            u'message_cost': decimal.Decimal('9.0'),
            u'message_direction': u'Inbound',
            u'session_cost': decimal.Decimal('7.0'),
            u'session_created': False,
            u'status': u'Completed',
            u'tag_name': u'12345',
            u'tag_pool_name': u'test_pool2',
        })

        # Test fallback to default cost
        yield self.create_api_cost(
            message_direction="Outbound",
            message_cost=0.1, session_cost=0.2,
            markup_percent=12.0)

        yield self.create_api_user(email="test5@example.com")
        account = yield self.create_api_account(
            email="test5@example.com", account_number="arbitrary-user")

        transaction = yield self.create_api_transaction(
            account_number="arbitrary-user",
            message_id='msg-id-4',
            tag_pool_name="some-random-pool",
            tag_name="erk",
            message_direction="Outbound",
            session_created=False)

        credit_amount = MessageCost.calculate_credit_cost(
            decimal.Decimal('0.1'), decimal.Decimal('12.0'),
            decimal.Decimal('0.2'), session_created=False)

        del (transaction['id'], transaction['created'],
             transaction['last_modified'])
        self.assertEqual(transaction, {
            u'account_number': 'arbitrary-user',
            u'message_id': 'msg-id-4',
            u'credit_amount': -credit_amount,
            u'credit_factor': decimal.Decimal('10.0'),
            u'markup_percent': decimal.Decimal('12.0'),
            u'message_cost': decimal.Decimal('0.1'),
            u'message_direction': u'Outbound',
            u'session_cost': decimal.Decimal('0.2'),
            u'session_created': False,
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
        except ApiCallError, e:
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
        except ApiCallError, e:
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
