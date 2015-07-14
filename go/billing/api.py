import json
import math

from decimal import Decimal

from twisted.python import log
from twisted.internet import defer
from twisted.internet.threads import deferToThread
from twisted.web.resource import Resource
from twisted.web.server import NOT_DONE_YET
from txpostgres.txpostgres import Connection, ConnectionPool
from txpostgres.reconnection import ConnectionDead, DeadConnectionDetector
# Import psycopg2 via txpostgres because they handle multiple implementations.
from txpostgres.txpostgres import psycopg2
import psycopg2.extras

from go.billing import settings as app_settings
from go.billing.models import MessageCost
from go.billing.utils import JSONEncoder, JSONDecoder, BillingError
from go.billing.tasks import create_low_credit_notification
from go.vumitools.billing_worker import BillingDispatcher

MESSAGE_DIRECTION_OUTBOUND = BillingDispatcher.MESSAGE_DIRECTION_OUTBOUND


def spawn_celery_task_via_thread(t, *args, **kw):
    """
    Issue a task to a Celery worker using deferToThread.

    :param Task t:
        The Celery task to issue.
    :param list args:
        Postional arguments for the Celery task.
    :param dict kw:
        Keyword arguments for the Celery task.
    """
    return deferToThread(t.delay, *args, **kw)


def pluck(data, keys):
    return (data[k] for k in keys)


class BaseResource(Resource):
    """Base class for the APIs ``Resource``s"""

    _connection_pool = None  # The txpostgres connection pool

    def __init__(self, connection_pool):
        Resource.__init__(self)
        self._connection_pool = connection_pool

    def _handle_error(self, error, request, *args, **kwargs):
        """Log the error and return an HTTP 500 response"""
        log.err(error)
        request.setResponseCode(500)  # Internal Server Error
        request.write(error.getErrorMessage())
        request.finish()

    def _handle_bad_request(self, request, *args, **kwargs):
        """Handle a bad request"""
        request.setResponseCode(400)  # Bad Request
        request.finish()

    def _render_to_json(self, result, request, *args, **kwargs):
        """Render the ``result`` as a JSON string.

        If the result is ``None`` return an HTTP 404 response.

        """
        if result is not None:
            data = json.dumps(result, cls=JSONEncoder)
            request.setResponseCode(200)  # OK
            request.setHeader('Content-Type', 'application/json')
            request.write(data)
        else:
            request.setResponseCode(404)  # Not Found
        request.finish()

    def _parse_json(self, request):
        """Return the POSTed data as a JSON object.

        If the *Content-Type* is anything other than *application/json*
        return ``None``.

        """
        content_type = request.getHeader('Content-Type')
        if request.method == 'POST' and content_type == 'application/json':
            content = request.content.read()
            return json.loads(content, cls=JSONDecoder)
        return None


class TransactionResource(BaseResource):
    """Expose a REST interface for a transaction"""

    isLeaf = True

    FIELDS = (
        'account_number', 'message_id', 'tag_pool_name',
        'tag_name', 'provider', 'message_direction',
        'session_created', 'session_length',
        'transaction_type')

    NULLABLE_FIELDS = ('provider', 'session_length')
    NON_NULLABLE_FIELDS = tuple(set(FIELDS) - set(NULLABLE_FIELDS))

    def __init__(self, connection_pool):
        BaseResource.__init__(self, connection_pool)
        self._notification_mapping = self._create_notification_mapping()

    def _create_notification_mapping(self):
        """
        Constructs a mapping from precentage of credits used to the
        notification percentage immediately above it.

        Only percentages from the lowest percentage to the highest percentage
        (inclusive) are entered in the mapping.
        """
        levels = sorted(
            int(i) for i in app_settings.LOW_CREDIT_NOTIFICATION_PERCENTAGES)

        if not levels:
            return []

        mapping = []
        level_idx = 0

        for i in range(levels[0], levels[-1] + 1):
            mapping.append(levels[level_idx])
            if mapping[i - levels[0]] == i:
                level_idx += 1

        return mapping

    def render_POST(self, request):
        """Handle an HTTP POST request"""
        data = self._parse_post(request)

        if data is None:
            self._handle_bad_request(request)
        else:
            d = self.create_transaction(*pluck(data, self.FIELDS))

            d.addCallbacks(self._render_to_json, self._handle_error,
                           callbackArgs=[request], errbackArgs=[request])

        return NOT_DONE_YET

    def _parse_post(self, request):
        data = self._parse_json(request) or {}
        data = dict((k, data.get(k)) for k in self.FIELDS)

        if any(data[k] is None for k in self.NON_NULLABLE_FIELDS):
            return None

        return data

    @defer.inlineCallbacks
    def get_cost(self, account_number, tag_pool_name, provider,
                 message_direction, session_created, session_length):
        """Return the message cost"""
        query = """
            SELECT t.account_number, t.tag_pool_name,
                   t.provider, t.message_direction,
                   t.message_cost, t.storage_cost, t.session_cost,
                   t.session_unit_time, t.session_unit_cost,
                   t.markup_percent
            FROM (SELECT a.account_number, t.name AS tag_pool_name,
                         c.provider, c.message_direction,
                         c.message_cost, c.storage_cost, c.session_cost,
                         c.session_unit_time, c.session_unit_cost,
                         c.markup_percent
                  FROM billing_messagecost c
                  LEFT OUTER JOIN billing_tagpool t ON (c.tag_pool_id = t.id)
                  LEFT OUTER JOIN billing_account a ON (c.account_id = a.id)
                  WHERE
                      (a.account_number = %(account_number)s OR
                       c.account_id IS NULL)
                      AND
                      (t.name = %(tag_pool_name)s OR c.tag_pool_id IS NULL)
                      AND
                      (c.provider = %(provider)s OR c.provider IS NULL)
                      AND
                      (c.message_direction = %(message_direction)s)
            ) as t
            ORDER BY
                t.account_number NULLS LAST,
                t.tag_pool_name NULLS LAST,
                t.provider NULLS LAST
            LIMIT 1
        """

        params = {
            'account_number': account_number,
            'tag_pool_name': tag_pool_name,
            'provider': provider,
            'message_direction': message_direction,
        }

        result = yield self._connection_pool.runQuery(query, params)
        if len(result) > 0:
            message_cost = result[0]
            message_cost['credit_amount'] = MessageCost.calculate_credit_cost(
                message_cost=message_cost['message_cost'],
                storage_cost=message_cost['storage_cost'],
                session_cost=message_cost['session_cost'],
                session_unit_length=message_cost['session_unit_time'],
                session_unit_cost=message_cost['session_unit_cost'],
                session_length=session_length,
                markup_percent=message_cost['markup_percent'],
                session_created=session_created)

            defer.returnValue(message_cost)
        else:
            defer.returnValue(None)

    @defer.inlineCallbacks
    def create_transaction_interaction(self, cursor, account_number,
                                       message_id, tag_pool_name, tag_name,
                                       provider, message_direction,
                                       session_created, session_length,
                                       transaction_type):
        """Create a new transaction for the given ``account_number``"""
        # Get the message cost
        result = yield self.get_cost(account_number, tag_pool_name, provider,
                                     message_direction, session_created,
                                     session_length)
        if result is None:
            raise BillingError(
                "Unable to determine %s message cost for account %s"
                " and tag pool %s" % (
                    message_direction, account_number, tag_pool_name))

        message_cost = result.get('message_cost', 0)
        session_cost = result.get('session_cost', 0)
        storage_cost = result.get('storage_cost', 0)
        session_unit_cost = result.get('session_unit_cost', 0)
        session_unit_time = result.get('session_unit_time', 0)
        markup_percent = result.get('markup_percent', 0)
        credit_amount = result.get('credit_amount', 0)

        session_len_cost = MessageCost.calculate_session_length_cost(
            session_unit_cost, session_unit_time, session_length)

        message_credits = MessageCost.calculate_message_credit_cost(
            message_cost, markup_percent)

        storage_credits = MessageCost.calculate_storage_credit_cost(
            storage_cost, markup_percent)

        session_credits = MessageCost.calculate_session_credit_cost(
            session_cost, markup_percent)

        session_len_credits = MessageCost.calculate_session_length_credit_cost(
            session_len_cost, markup_percent)

        query = """SELECT credit_balance, last_topup_balance
                   FROM billing_account
                   WHERE account_number = %(account_number)s"""

        params = {'account_number': account_number}
        cursor = yield cursor.execute(query, params)
        result = yield cursor.fetchone()

        if result is None:
            raise BillingError(
                "Unable to find billing account %s while checking"
                " credit balance. Message was %s to/from tag pool %s." % (
                    account_number, message_direction, tag_pool_name))

        last_topup_balance = result.get('last_topup_balance')
        credit_balance = result.get('credit_balance')

        # If the message is outbound and limit is reached, don't charge
        if (app_settings.ENABLE_LOW_CREDIT_CUTOFF and last_topup_balance and
                message_direction == MESSAGE_DIRECTION_OUTBOUND):
            if (self._ceil_percent(credit_balance, last_topup_balance) <
                    self._notification_mapping[0]):
                defer.returnValue({
                    'credit_cutoff_reached': True,
                    'transaction': None,
                })

        # Create a new transaction
        query = """
            INSERT INTO billing_transaction
                (account_number, message_id, transaction_type,
                 tag_pool_name, tag_name,
                 provider, message_direction,
                 message_cost, storage_cost, session_cost,
                 session_unit_cost, session_length_cost,
                 session_created, markup_percent,
                 message_credits, storage_credits, session_credits,
                 session_length_credits,
                 credit_factor, credit_amount,
                 session_unit_time, session_length,
                 status, created, last_modified)
            VALUES
                (%(account_number)s, %(message_id)s, %(transaction_type)s,
                 %(tag_pool_name)s, %(tag_name)s,
                 %(provider)s, %(message_direction)s,
                 %(message_cost)s, %(storage_cost)s, %(session_cost)s,
                 %(session_unit_cost)s, %(session_length_cost)s,
                 %(session_created)s, %(markup_percent)s,
                 %(message_credits)s, %(storage_credits)s, %(session_credits)s,
                 %(session_length_credits)s,
                 %(credit_factor)s, %(credit_amount)s,
                 %(session_unit_time)s, %(session_length)s,
                 'Completed', now(), now())
            RETURNING id, account_number, message_id, transaction_type,
                      tag_pool_name, tag_name,
                      provider, message_direction,
                      message_cost, storage_cost, session_cost,
                      session_unit_cost, session_length_cost,
                      session_created, markup_percent,
                      message_credits, storage_credits, session_credits,
                      session_length_credits,
                      credit_factor, credit_amount,
                      session_unit_time, session_length,
                      status, created, last_modified
        """

        params = {
            'account_number': account_number,
            'message_id': message_id,
            'transaction_type': transaction_type,
            'tag_pool_name': tag_pool_name,
            'tag_name': tag_name,
            'provider': provider,
            'message_direction': message_direction,
            'message_cost': message_cost,
            'storage_cost': storage_cost,
            'session_created': session_created,
            'session_cost': session_cost,
            'session_unit_cost': session_unit_cost,
            'session_length_cost': session_len_cost,
            'markup_percent': markup_percent,
            'message_credits': message_credits,
            'storage_credits': storage_credits,
            'session_credits': session_credits,
            'session_length_credits': session_len_credits,
            'credit_factor': app_settings.CREDIT_CONVERSION_FACTOR,
            'credit_amount': -credit_amount,
            'session_unit_time': session_unit_time,
            'session_length': session_length,
        }

        cursor = yield cursor.execute(query, params)
        transaction = yield cursor.fetchone()

        # Update the account's credit balance
        query = """
            UPDATE billing_account
            SET credit_balance = credit_balance - %(credit_amount)s
            WHERE account_number = %(account_number)s
            RETURNING credit_balance
        """

        params = {
            'credit_amount': credit_amount,
            'account_number': account_number
        }

        cursor = yield cursor.execute(query, params)
        result = cursor.fetchone()

        # Check the account's credit balance and raise an
        # alert if it has gone below the credit balance threshold
        if result is None:
            raise BillingError(
                "Unable to find billing account %s while checking"
                " credit balance. Message was %s to/from tag pool %s." % (
                    account_number, message_direction, tag_pool_name))

        credit_balance = result.get('credit_balance')

        if app_settings.ENABLE_LOW_CREDIT_NOTIFICATION:
            yield self.check_and_notify_low_credit_threshold(
                credit_balance, credit_amount, last_topup_balance,
                account_number)

        if app_settings.ENABLE_LOW_CREDIT_CUTOFF and last_topup_balance:
            if (self._ceil_percent(credit_balance, last_topup_balance) <
                    self._notification_mapping[0]):
                defer.returnValue({
                    'transaction': transaction,
                    'credit_cutoff_reached': True,
                })

        defer.returnValue({
            'transaction': transaction,
            'credit_cutoff_reached': False,
        })

    def check_and_notify_low_credit_threshold(
            self, credit_balance, credit_amount, last_topup_balance,
            account_number):
        """
        Checks the current balance percentage against all those stored within
        the settings. Sends the notification email if it is required. Returns
        the alert percent if email was sent, or ``None`` if no email was sent.

        :param credit_balance: The current balance (after the transaction)
        :param credit_amount: The amount of credits used in the transaction
        :param last_topup_balance: The account credit balance at the last topup
        :param account_number: The account number of the associated account
        """
        level = self.check_all_low_credit_thresholds(
            credit_balance, credit_amount, last_topup_balance)
        if level is not None:
            cutoff_notification = level * 100 == self._notification_mapping[0]
            return spawn_celery_task_via_thread(
                create_low_credit_notification, account_number,
                level, credit_balance, cutoff_notification)

    def _get_notification_level(self, percentage):
        """
        Fetches the value of the notification level for the given percentage.

        :param int percentage:
            The percentage to get the notification level for

        :return:
            An int representing the current notification level.
        """
        if not self._notification_mapping:
            return None

        minimum = self._notification_mapping[0]
        if percentage < minimum:
            return minimum
        if percentage > self._notification_mapping[-1]:
            return None
        return self._notification_mapping[percentage - minimum]

    def _ceil_percent(self, num, den):
        return int(math.ceil(num * 100 / den))

    def check_all_low_credit_thresholds(
            self, credit_balance, credit_amount, last_topup_balance):
        """
        Checks the current balance percentage against all those stored within
        the settings.

        :param credit_balance:
            The current balance (after the transaction)
        :param credit_amount:
            The amount of credits used in the transaction
        :param last_topup_balance:
            The account credit balance at the last topup

        :return:
            A :class:`Decimal` percentage for the alert threshold crossed
            or ``None`` if no threshold was crossed.
        """
        if not last_topup_balance:
            return None

        def ceil_percent(n):
            return self._ceil_percent(n, last_topup_balance)

        current_percentage = ceil_percent(credit_balance)
        current_notification_level = self._get_notification_level(
            current_percentage)
        previous_percentage = ceil_percent(credit_balance + credit_amount)
        previous_notification_level = self._get_notification_level(
            previous_percentage)

        if current_notification_level != previous_notification_level:
            return Decimal(str(current_notification_level / 100.0))

    @defer.inlineCallbacks
    def create_transaction(self, account_number, message_id, tag_pool_name,
                           tag_name, provider, message_direction,
                           session_created, session_length, transaction_type):
        """Create a new transaction for the given ``account_number``"""
        result = yield self._connection_pool.runInteraction(
            self.create_transaction_interaction, account_number, message_id,
            tag_pool_name, tag_name, provider, message_direction,
            session_created, session_length, transaction_type)

        defer.returnValue(result)


class HealthResource(Resource):
    isLeaf = True

    def __init__(self, health_check_func):
        Resource.__init__(self)
        self._health_check_func = health_check_func

    def render_GET(self, request):
        self._render_health_check(request)
        return NOT_DONE_YET

    @defer.inlineCallbacks
    def _render_health_check(self, request):
        code, content = yield self._health_check_func()
        request.setResponseCode(code)
        request.write(content + "\n")
        request.finish()


class Root(BaseResource):
    """The root resource"""

    def __init__(self, connection_pool):
        BaseResource.__init__(self, connection_pool)
        self.putChild('transactions', TransactionResource(connection_pool))
        self.putChild('health', HealthResource(self.health_check))

    def getChild(self, name, request):
        if name == '':
            return self
        return Resource.getChild(self, name, request)

    def render_GET(self, request):
        request.setResponseCode(200)  # OK
        return ''

    @defer.inlineCallbacks
    def health_check(self):
        """
        We want our health check to be comprehensive, so we implement it here.
        """
        try:
            yield self._connection_pool.runQuery("SELECT 1")
        except (ConnectionDead, psycopg2.InterfaceError):
            defer.returnValue((503, "Database connection unavailable"))
        # Everything's happy.
        defer.returnValue((200, "OK"))


def billing_api_resource():
    """
    Create and return a go.billing.api.Root resource for use with twistd.
    """
    connection_string = app_settings.get_connection_string()
    connection_pool = DictRowConnectionPool(
        None, connection_string, min=app_settings.API_MIN_CONNECTIONS)
    resource = Root(connection_pool)
    # Tests need to know when we're connected, so stash the deferred on the
    # resource for them to look at.
    resource._connection_pool_started = connection_pool.start()
    return resource


def real_dict_connect(*args, **kwargs):
    kwargs['connection_factory'] = psycopg2.extras.RealDictConnection
    return psycopg2.connect(*args, **kwargs)


class DictRowConnection(Connection):
    """Extend the txpostgres ``Connection`` and override the
    ``cursorFactory``

    """

    connectionFactory = staticmethod(real_dict_connect)

    def __init__(self, *args, **kw):
        super(DictRowConnection, self).__init__(*args, **kw)
        if self.detector is None:
            self.detector = DeadConnectionDetector()

    def connect(self, *args, **kw):
        d = super(DictRowConnection, self).connect(*args, **kw)
        # We set self.detector in __init__ if there isn't one already.
        d.addErrback(self.detector.checkForDeadConnection)
        return d

    @property
    def closed(self):
        """Return ``True`` if the underlying connection is closed
        ``False`` otherwise

        """
        if self._connection:
            return self._connection.closed
        return True


class DictRowConnectionPool(ConnectionPool):
    """Extend the txpostgres ``ConnectionPool`` and override the
    ``connectionFactory``

    """

    connectionFactory = DictRowConnection

    @property
    def closed(self):
        """Return ``True`` all the connections are closed
        ``False`` otherwise

        """
        return all(c.closed for c in self.connections)
