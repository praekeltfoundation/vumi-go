import json
from decimal import Decimal

import mock
import pytest

from twisted.internet.defer import inlineCallbacks, returnValue

from vumi.tests.helpers import VumiTestCase

from go.billing import settings as app_settings
from go.billing import api
from go.billing.models import Account, Transaction, MessageCost
from go.billing.utils import DummySite, DictRowConnectionPool, JSONDecoder
from go.base.tests.helpers import DjangoVumiApiHelper
from go.billing.django_utils import load_account_credits
from go.billing.tests.helpers import (
    mk_tagpool, mk_message_cost, get_session_length_cost,
    get_message_credits, get_storage_credits, get_session_credits,
    get_session_length_credits)

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
@pytest.mark.django_db(transaction=True)
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
        yield super(BillingApiTestCase, self).tearDown()
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


class TestTransaction(BillingApiTestCase):

    def setUp(self):
        self.patch(
            app_settings,
            'LOW_CREDIT_NOTIFICATION_PERCENTAGES',
            [70, 90, 80])

        vumi_helper = self.add_helper(DjangoVumiApiHelper())

        self.account = Account.objects.get(
            user=vumi_helper.make_django_user().get_django_user())

        self.account2 = Account.objects.get(
            user=vumi_helper.make_django_user(u'user2').get_django_user())

        self.pool1 = mk_tagpool('pool1')
        self.pool2 = mk_tagpool('pool2')

        return BillingApiTestCase.setUp(self)

    def create_api_transaction(self, **kwargs):
        """
        Create a transaction record via the billing API.
        """
        content = {
            'account_number': self.account.account_number,
            'message_id': 'msg-id-1',
            'tag_pool_name': 'pool1',
            'tag_name': 'tag1',
            'message_direction': MessageCost.DIRECTION_INBOUND,
            'session_created': False,
            'provider': None,
            'transaction_type': Transaction.TRANSACTION_TYPE_MESSAGE,
            'session_length': None,
        }
        content.update(kwargs)
        return self.call_api('post', 'transactions', content=content)

    def assert_dict(self, dict_obj, **kw):
        for name, value in kw.iteritems():
            self.assertEqual(dict_obj[name], value)

    def assert_model(self, model, **kw):
        for name, value in kw.iteritems():
            self.assertEqual(getattr(model, name), value)

    def assert_result(self, result, model, **kw):
        self.assert_dict(result, **kw)
        self.assert_model(model, **kw)

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
        account = self.account

        # patch settings and task
        mock_task_delay = mock.MagicMock()
        self.patch(app_settings, 'ENABLE_LOW_CREDIT_NOTIFICATION', True)
        self.patch(
            api.create_low_credit_notification, 'delay', mock_task_delay)

        # Load credits
        load_account_credits(account, 10)

        # Set the message cost
        mk_message_cost(
            tag_pool=self.pool1,
            message_direction=MessageCost.DIRECTION_INBOUND,
            message_cost=0.1,
            session_cost=0.1,
            markup_percent=0.1)

        # Create a transaction
        yield self.create_api_transaction(
            account_number=account.account_number,
            message_id='msg-id-1',
            tag_pool_name='pool1',
            tag_name='tag1',
            message_direction=MessageCost.DIRECTION_INBOUND,
            session_created=False)

        # It should create the first notification
        account = Account.objects.get(id=account.id)
        mock_task_delay.assert_called_once_with(
            account.account_number,
            Decimal('0.9'),
            account.credit_balance)
        mock_task_delay.reset_mock()

        # Create another transaction
        yield self.create_api_transaction(
            account_number=account.account_number,
            message_id='msg-id-2',
            tag_pool_name='pool1',
            tag_name='tag1',
            message_direction=MessageCost.DIRECTION_INBOUND,
            session_created=False)

        # It should create the second notification
        account = Account.objects.get(id=account.id)
        mock_task_delay.assert_called_once_with(
            account.account_number,
            Decimal('0.8'),
            account.credit_balance)
        mock_task_delay.reset_mock()

        # Create a third transaction
        yield self.create_api_transaction(
            account_number=account.account_number,
            message_id='msg-id-2',
            tag_pool_name='pool1',
            tag_name='tag1',
            message_direction=MessageCost.DIRECTION_INBOUND,
            session_created=False)

        # It should create the third notification
        account = Account.objects.get(id=account.id)
        mock_task_delay.assert_called_once_with(
            account.account_number,
            Decimal('0.7'),
            account.credit_balance)
        mock_task_delay.reset_mock()

        # Create a fourth transaction
        yield self.create_api_transaction(
            account_number=account.account_number,
            message_id='msg-id-2',
            tag_pool_name='pool1',
            tag_name='tag1',
            message_direction=MessageCost.DIRECTION_INBOUND,
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

        self.assertEqual(self.account.last_topup_balance, Decimal('0.0'))

        # Set the message cost
        mk_message_cost(
            tag_pool=self.pool1,
            message_direction=MessageCost.DIRECTION_INBOUND,
            message_cost=0.1,
            session_cost=0.1,
            markup_percent=0.1)

        # Create a transaction
        yield self.create_api_transaction(
            account_number=self.account.account_number,
            message_id='msg-id-1',
            tag_pool_name='pool1',
            tag_name='tag1',
            message_direction=MessageCost.DIRECTION_INBOUND,
            session_created=False)

        self.assertFalse(mock_task_delay.called)

    @inlineCallbacks
    def test_credit_cutoff_inbound(self):
        self.patch(app_settings, 'ENABLE_LOW_CREDIT_CUTOFF', True)

        mk_message_cost(
            tag_pool=self.pool1,
            message_direction=MessageCost.DIRECTION_INBOUND,
            message_cost=0.2,
            storage_cost=0.0,
            session_cost=0.0,
            markup_percent=0.0)

        load_account_credits(self.account, 10)

        transaction1 = yield self.create_api_transaction(
            account_number=self.account.account_number,
            message_id='msg-id-1',
            tag_pool_name='pool1',
            tag_name='tag1',
            message_direction=MessageCost.DIRECTION_INBOUND,
            session_created=False,
            transaction_type=Transaction.TRANSACTION_TYPE_MESSAGE)

        self.assertFalse(transaction1.get('credit_cutoff_reached', False))
        self.assertEqual(Transaction.objects.count(), 2)

        transaction2 = yield self.create_api_transaction(
            account_number=self.account.account_number,
            message_id='msg-id-1',
            tag_pool_name='pool1',
            tag_name='tag1',
            message_direction=MessageCost.DIRECTION_INBOUND,
            session_created=False,
            transaction_type=Transaction.TRANSACTION_TYPE_MESSAGE)

        self.assertTrue(transaction2.get('credit_cutoff_reached', False))
        self.assertEqual(Transaction.objects.count(), 3)

        @inlineCallbacks
        def test_credit_cutoff_outbound(self):
            self.patch(app_settings, 'ENABLE_LOW_CREDIT_CUTOFF', True)

            mk_message_cost(
                tag_pool=self.pool1,
                message_direction=MessageCost.DIRECTION_OUTBOUND,
                message_cost=0.2,
                storage_cost=0.0,
                session_cost=0.0,
                markup_percent=0.0)

            load_account_credits(self.account, 10)

            transaction1 = yield self.create_api_transaction(
                account_number=self.account.account_number,
                message_id='msg-id-1',
                tag_pool_name='pool1',
                tag_name='tag1',
                message_direction=MessageCost.DIRECTION_OUTBOUND,
                session_created=False,
                transaction_type=Transaction.TRANSACTION_TYPE_MESSAGE)

            self.assertFalse(transaction1.get('credit_cutoff_reached', False))
            self.assertEqual(Transaction.objects.count(), 2)

            transaction2 = yield self.create_api_transaction(
                account_number=self.account.account_number,
                message_id='msg-id-1',
                tag_pool_name='pool1',
                tag_name='tag1',
                message_direction=MessageCost.DIRECTION_OUTBOUND,
                session_created=False,
                transaction_type=Transaction.TRANSACTION_TYPE_MESSAGE)

            self.assertTrue(transaction2.get('credit_cutoff_reached', False))
            self.assertEqual(Transaction.objects.count(), 2)

    @inlineCallbacks
    def test_transaction(self):
        account = self.account
        account2 = self.account2

        # Set the message cost
        mk_message_cost(
            tag_pool=self.pool1,
            message_direction=MessageCost.DIRECTION_INBOUND,
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
        transaction = yield self.create_api_transaction(
            account_number=account.account_number,
            message_id='msg-id-1',
            tag_pool_name='pool1',
            tag_name='tag1',
            message_direction=MessageCost.DIRECTION_INBOUND,
            session_created=False,
            transaction_type=Transaction.TRANSACTION_TYPE_MESSAGE)

        self.assert_result(
            result=transaction,
            model=Transaction.objects.latest('created'),
            message_id='msg-id-1',
            tag_name='tag1',
            tag_pool_name='pool1',
            account_number=account.account_number,
            credit_amount=-credit_amount,
            credit_factor=Decimal('10.0'),
            markup_percent=Decimal('10.0'),
            message_cost=Decimal('0.6'),
            storage_cost=Decimal('0.5'),
            session_cost=Decimal('0.3'),
            session_created=False,
            message_credits=get_message_credits(0.6, 10.0),
            storage_credits=get_storage_credits(0.5, 10.0),
            session_credits=get_session_credits(0.3, 10.0),
            status=Transaction.STATUS_COMPLETED,
            message_direction=MessageCost.DIRECTION_INBOUND,
            transaction_type=Transaction.TRANSACTION_TYPE_MESSAGE)

        # Get the account and make sure the credit balance was updated
        account = Account.objects.get(id=account.id)
        self.assertEqual(account.credit_balance, -credit_amount)

        # Create a transaction (with session_created=True)
        transaction = yield self.create_api_transaction(
            account_number=account.account_number,
            message_id='msg-id-2',
            tag_pool_name='pool1',
            tag_name='tag1',
            message_direction=MessageCost.DIRECTION_INBOUND,
            session_created=True)

        self.assert_result(
            result=transaction,
            model=Transaction.objects.latest('created'),
            message_id='msg-id-2',
            tag_name='tag1',
            tag_pool_name='pool1',
            account_number=account.account_number,
            credit_amount=-credit_amount_for_session,
            credit_factor=Decimal('10.0'),
            markup_percent=Decimal('10.0'),
            message_cost=Decimal('0.6'),
            storage_cost=Decimal('0.5'),
            session_cost=Decimal('0.3'),
            session_created=True,
            message_credits=get_message_credits(0.6, 10.0),
            storage_credits=get_storage_credits(0.5, 10.0),
            session_credits=get_session_credits(0.3, 10.0),
            status=Transaction.STATUS_COMPLETED,
            message_direction=MessageCost.DIRECTION_INBOUND)

        # Get the account and make sure the credit balance was updated
        account = Account.objects.get(id=account.id)
        self.assertEqual(account.credit_balance,
                         -(credit_amount + credit_amount_for_session))

        # Test override of cost by cost for specific account
        mk_message_cost(
            account=account,
            tag_pool=self.pool1,
            message_direction=MessageCost.DIRECTION_INBOUND,
            message_cost=9.0,
            storage_cost=8.0,
            session_cost=7.0,
            markup_percent=11.0)

        transaction = yield self.create_api_transaction(
            account_number=account.account_number,
            message_id='msg-id-3',
            tag_pool_name='pool1',
            tag_name='tag1',
            message_direction=MessageCost.DIRECTION_INBOUND,
            session_created=False)

        credit_amount = MessageCost.calculate_credit_cost(
            Decimal('9.0'),
            Decimal('8.0'),
            Decimal('11.0'),
            Decimal('7.0'),
            session_created=False)

        self.assert_result(
            result=transaction,
            model=Transaction.objects.latest('created'),
            message_id='msg-id-3',
            tag_name='tag1',
            tag_pool_name='pool1',
            account_number=account.account_number,
            credit_amount=-credit_amount,
            credit_factor=Decimal('10.0'),
            markup_percent=Decimal('11.0'),
            message_cost=Decimal('9.0'),
            storage_cost=Decimal('8.0'),
            session_cost=Decimal('7.0'),
            session_created=False,
            message_credits=get_message_credits(9.0, 11.0),
            storage_credits=get_storage_credits(8.0, 11.0),
            session_credits=get_session_credits(7.0, 11.0),
            status=Transaction.STATUS_COMPLETED,
            message_direction=MessageCost.DIRECTION_INBOUND)

        # Test fallback to default cost
        mk_message_cost(
            message_direction=MessageCost.DIRECTION_OUTBOUND,
            message_cost=0.1,
            storage_cost=0.3,
            session_cost=0.2,
            markup_percent=12.0)

        transaction = yield self.create_api_transaction(
            account_number=account2.account_number,
            message_id='msg-id-4',
            tag_pool_name='pool2',
            tag_name='tag2',
            message_direction=MessageCost.DIRECTION_OUTBOUND,
            session_created=False)

        credit_amount = MessageCost.calculate_credit_cost(
            Decimal('0.1'),
            Decimal('0.3'),
            Decimal('12.0'),
            Decimal('0.2'),
            session_created=False)

        self.assert_result(
            result=transaction,
            model=Transaction.objects.latest('created'),
            message_id='msg-id-4',
            tag_name='tag2',
            tag_pool_name='pool2',
            account_number=account2.account_number,
            credit_amount=-credit_amount,
            credit_factor=Decimal('10.0'),
            markup_percent=Decimal('12.0'),
            message_cost=Decimal('0.1'),
            storage_cost=Decimal('0.3'),
            session_cost=Decimal('0.2'),
            session_created=False,
            message_credits=get_message_credits(0.1, 12.0),
            storage_credits=get_storage_credits(0.3, 12.0),
            session_credits=get_session_credits(0.2, 12.0),
            status=Transaction.STATUS_COMPLETED,
            message_direction=MessageCost.DIRECTION_OUTBOUND)

        # Test that message direction is correctly checked for
        # in the fallback case.
        try:
            yield self.create_api_transaction(
                account_number=account2.account_number,
                message_id='msg-id-4',
                tag_pool_name='pool2',
                tag_name='tag2',
                message_direction=MessageCost.DIRECTION_INBOUND,
                session_created=False)
        except ApiCallError as e:
            self.assertEqual(e.response.responseCode, 500)
            self.assertEqual(
                e.message,
                "Unable to determine Inbound message cost for account"
                " %s and tag pool pool2" % (account2.account_number,))
        else:
            self.fail("Expected transaction creation to fail.")

        [failure] = self.flushLoggedErrors('go.billing.utils.BillingError')
        self.assertEqual(
            failure.value.args,
            ("Unable to determine Inbound message cost for account"
                " %s and tag pool pool2" % (account2.account_number,),))

        # Test that transactions for unknown accounts raised a BillingError
        try:
            yield self.create_api_transaction(
                account_number='unknown-account',
                message_id='msg-id-5',
                tag_pool_name='pool2',
                tag_name='tag2',
                message_direction=MessageCost.DIRECTION_OUTBOUND,
                session_created=False)
        except ApiCallError as e:
            self.assertEqual(e.response.responseCode, 500)
            self.assertEqual(
                e.message,
                "Unable to find billing account unknown-account while"
                " checking credit balance. Message was Outbound to/from"
                " tag pool pool2.")
        else:
            self.fail("Expected transaction creation to fail.")

        [failure] = self.flushLoggedErrors('go.billing.utils.BillingError')
        self.assertEqual(
            failure.value.args,
            ("Unable to find billing account unknown-account while"
             " checking credit balance. Message was Outbound to/from"
             " tag pool pool2.",))

    @inlineCallbacks
    def test_transaction_provider(self):
        mk_message_cost(tag_pool=self.pool1)

        transaction = yield self.create_api_transaction(
            account_number=self.account.account_number,
            provider='mtn')

        self.assert_result(
            result=transaction,
            model=Transaction.objects.latest('created'),
            provider='mtn')

    @inlineCallbacks
    def test_transaction_provider_none(self):
        mk_message_cost(tag_pool=self.pool1)

        transaction = yield self.create_api_transaction(
            account_number=self.account.account_number,
            provider=None)

        self.assert_result(
            result=transaction,
            model=Transaction.objects.latest('created'),
            provider=None)

    @inlineCallbacks
    def test_transaction_provider_cost(self):
        mk_message_cost(
            tag_pool=self.pool1,
            message_cost=0.8,
            provider=None)

        mk_message_cost(
            tag_pool=self.pool1,
            message_cost=0.7,
            provider='vodacom')

        mk_message_cost(
            tag_pool=self.pool1,
            message_cost=0.6,
            provider='mtn')

        transaction = yield self.create_api_transaction(
            account_number=self.account.account_number,
            provider='mtn')

        self.assert_result(
            result=transaction,
            model=Transaction.objects.latest('created'),
            message_cost=Decimal('0.6'))

        transaction = yield self.create_api_transaction(
            account_number=self.account.account_number,
            provider='vodacom')

        self.assert_result(
            result=transaction,
            model=Transaction.objects.latest('created'),
            message_cost=Decimal('0.7'))

    @inlineCallbacks
    def test_transaction_provider_fallback_cost(self):
        mk_message_cost(
            tag_pool=self.pool1,
            message_cost=0.8,
            provider=None)

        mk_message_cost(
            tag_pool=self.pool1,
            message_cost=0.6,
            provider='mtn')

        transaction = yield self.create_api_transaction(
            account_number=self.account.account_number,
            provider='unknown')

        self.assert_result(
            result=transaction,
            model=Transaction.objects.latest('created'),
            message_cost=Decimal('0.8'))

        transaction = yield self.create_api_transaction(
            account_number=self.account.account_number,
            provider=None)

        self.assert_result(
            result=transaction,
            model=Transaction.objects.latest('created'),
            message_cost=Decimal('0.8'))

    @inlineCallbacks
    def test_transaction_session_length_cost(self):
        mk_message_cost(
            tag_pool=self.pool1,
            session_unit_cost=0.2,
            session_unit_time=20,
            markup_percent=10)

        transaction = yield self.create_api_transaction(
            account_number=self.account.account_number,
            session_length=23)

        session_length_cost = get_session_length_cost(0.2, 20, 23)

        self.assert_result(
            result=transaction,
            model=Transaction.objects.latest('created'),
            session_unit_cost=Decimal('0.2'),
            session_unit_time=Decimal('20.0'),
            session_length_cost=session_length_cost,
            session_length_credits=get_session_length_credits(
                session_length_cost, 10),
            session_length=Decimal('23.0'))

    @inlineCallbacks
    def test_transaction_session_length_cost_none_length(self):
        mk_message_cost(
            tag_pool=self.pool1,
            session_unit_cost=0.2,
            session_unit_time=20,
            markup_percent=10)

        transaction = yield self.create_api_transaction(
            account_number=self.account.account_number,
            session_length=None)

        self.assert_result(
            result=transaction,
            model=Transaction.objects.latest('created'),
            session_unit_cost=Decimal('0.2'),
            session_unit_time=Decimal('20.0'),
            session_length_cost=Decimal(0),
            session_length_credits=Decimal(0),
            session_length=None)
