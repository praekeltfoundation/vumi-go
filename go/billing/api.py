import json
import decimal
import datetime

import psycopg2
import psycopg2.extras

from txpostgres import txpostgres

from twisted.python import log, util
from twisted.internet import defer
from twisted.web.resource import Resource
from twisted.web.server import NOT_DONE_YET

from go.billing import settings as app_settings


class JSONEncoder(json.JSONEncoder):
    """JSONEncoder to handle ``Decimal`` and ``datetime`` values"""

    def default(self, obj):
        if isinstance(obj, decimal.Decimal):
            return float(obj.quantize(decimal.Decimal('.01')))
        elif isinstance(obj, datetime.datetime):
            return obj.isoformat()
        else:
            return json.JSONEncoder.default(self, obj)


def real_dict_connect(*args, **kwargs):
    kwargs['connection_factory'] = psycopg2.extras.RealDictConnection
    return psycopg2.connect(*args, **kwargs)


class RealDictConnection(txpostgres.Connection):
    """Extend the txpostgres ``Connection`` and override the
    ``cursorFactory``

    """

    connectionFactory = staticmethod(real_dict_connect)


class RealDictConnectionPool(txpostgres.ConnectionPool):
    """Extend the txpostgres ``ConnectionPool`` and override the
    ``connectionFactory``

    """

    connectionFactory = RealDictConnection

# Create the txpostgres connection pool
connection_pool = RealDictConnectionPool(
    None, app_settings.API_CONNECTION_STRING,
    min=app_settings.API_MIN_CONNECTIONS)


def handle_error(error, request, *args, **kwargs):
    """Log the error and return an HTTP 500 response"""
    log.err(error)
    request.setResponseCode(500)  # Internal Server Error
    request.finish()


def render_to_json(result, request, *args, **kwargs):
    """Render the ``result`` as a JSON string.

    If the result is ``None`` return an HTTP 404 response.

    """
    if result is not None:
        request.setHeader('Content-Type', 'application/json')
        request.write(json.dumps(result, cls=JSONEncoder))
    else:
        request.setResponseCode(404)  # Not Found
    request.finish()


def parse_json(request):
    """Return the POSTed data as a JSON object.

    If the *Content-Type* is anything other than *application/json*
    return ``None``

    """
    content_type = request.getHeader('Content-Type')
    if request.method == 'POST' and content_type == 'application/json':
        return json.loads(request.content.read(), parse_float=decimal.Decimal)
    return None


class Root(Resource):
    """The root resource"""

    def getChild(self, name, request):
        if name == '':
            return self
        return Resource.getChild(self, name, request)

    def render_GET(self, request):
        request.setResponseCode(200)  # OK
        return ''


class AccountResource(Resource):
    """Expose a REST interface for an account"""

    isLeaf = True

    def render_GET(self, request):
        """Handle an HTTP GET request"""
        params = filter(None, request.postpath)
        if len(params) > 0:
            d = self.get_account(params[0])
            d.addCallbacks(render_to_json, handle_error,
                           callbackArgs=[request], errbackArgs=[request])

        else:
            d = self.get_account_list()
            d.addCallbacks(render_to_json, handle_error,
                           callbackArgs=[request], errbackArgs=[request])

        return NOT_DONE_YET

    @defer.inlineCallbacks
    def get_account(self, account_number):
        """Fetch the account with the given ``account_number``"""
        query = """SELECT account_number, description, credit_balance,
                          alert_threshold, alert_credit_balance
                   FROM billing_account
                   WHERE account_number = %(account_number)s"""
        params = {'account_number': account_number}
        result = yield connection_pool.runQuery(query, params)
        if len(result) > 0:
            defer.returnValue(result[0])
        else:
            defer.returnValue(None)

    @defer.inlineCallbacks
    def get_account_list(self):
        """Fetch all accounts"""
        query = """SELECT account_number, description, credit_balance,
                          alert_threshold, alert_credit_balance
                   FROM billing_account"""
        result = yield connection_pool.runQuery(query)
        defer.returnValue(result)

    def render_POST(self, request):
        """Handle an HTTP POST request"""
        params = filter(None, request.postpath)
        if len(params) == 2:
            (account_number, path), rest = params[:2], params[2:]
            if path == 'credits':
                data = parse_json(request)
                d = self.load_credits(account_number,
                                      data.get('credit_amount', 0))

                d.addCallbacks(render_to_json, handle_error,
                               callbackArgs=[request], errbackArgs=[request])

                return NOT_DONE_YET
            else:
                request.setResponseCode(400)  # Bad Request
        else:
            request.setResponseCode(400)  # Bad Request
        return ''

    @defer.inlineCallbacks
    def load_credits_interaction(self, cursor, account_number, credit_amount):
        # Create a new transaction
        query = """INSERT INTO billing_transaction
                       (account_number, tag_pool_name, message_direction,
                        credit_amount, status, created, last_modified)
                   VALUES (%(account_number)s, '', '', %(credit_amount)s,
                          'Completed', now(), now())"""

        params = {
            'account_number': account_number,
            'credit_amount': credit_amount
        }

        cursor = yield cursor.execute(query, params)

        # Update the account's credit balance
        query = """
            UPDATE billing_account
            SET credit_balance = credit_balance + %(credit_amount)s,
                alert_credit_balance = (credit_balance + %(credit_amount)s)
                                       * alert_threshold / 100.0
            WHERE account_number = %(account_number)s
        """

        params = {
            'credit_amount': credit_amount,
            'account_number': account_number
        }

        cursor = yield cursor.execute(query, params)

        # Fetch the latest account information
        query = """SELECT account_number, description, credit_balance,
                          alert_threshold, alert_credit_balance
                   FROM billing_account
                   WHERE account_number = %(account_number)s"""

        params = {'account_number': account_number}
        cursor = yield cursor.execute(query, params)
        result = yield cursor.fetchone()
        defer.returnValue(result)

    @defer.inlineCallbacks
    def load_credits(self, account_number, credit_amount):
        """Load ``credit_value`` credits in the given ``account_number``"""
        result = yield connection_pool.runInteraction(
            self.load_credits_interaction, account_number, credit_amount)

        defer.returnValue(result)


class TransactionResource(Resource):
    """Expose a REST interface for a transaction"""

    isLeaf = True

    def render_GET(self, request):
        """Handle an HTTP GET request"""
        params = filter(None, request.postpath)
        if len(params) > 0 and params[0] == 'cost':
            account_number = request.args.get('account_number', [])
            tag_pool_name = request.args.get('tag_pool_name', [])
            message_direction = request.args.get('message_direction', [])
            if len(account_number) > 0 and len(tag_pool_name) > 0 \
                    and len(message_direction) > 0:
                d = self.get_cost(account_number[0], tag_pool_name[0],
                                  message_direction[0])

                d.addCallbacks(render_to_json, handle_error,
                               callbackArgs=[request], errbackArgs=[request])

                return NOT_DONE_YET
            else:
                request.setResponseCode(400)  # Bad Request
                return ''
        else:
            account_number = request.args.get('account_number', [])
            page_number = request.args.get('page_number', [0])
            items_per_page = request.args.get('items_per_page', [20])
            if len(account_number) > 0:
                d = self.get_transaction_list(
                    account_number[0], page_number[0], items_per_page[0])

                d.addCallbacks(render_to_json, handle_error,
                               callbackArgs=[request], errbackArgs=[request])

            else:
                request.setResponseCode(400)  # Bad Request
                return ''
            return NOT_DONE_YET

    def render_POST(self, request):
        """Handle an HTTP POST request"""
        data = parse_json(request)
        account_number = data.get('account_number', None)
        tag_pool_name = data.get('tag_pool_name', None)
        message_direction = data.get('message_direction', None)
        if account_number and tag_pool_name and message_direction:
            d = self.create_transaction(
                account_number, tag_pool_name, message_direction)

            d.addCallbacks(render_to_json, handle_error,
                           callbackArgs=[request], errbackArgs=[request])

            return NOT_DONE_YET
        else:
            request.setResponseCode(400)  # Bad Request
            return ''

    @defer.inlineCallbacks
    def get_cost(self, account_number, tag_pool_name, message_direction):
        """Return the message cost"""
        # Check for a account cost override
        query = """
            SELECT c.message_cost, c.markup_percent,
                   (c.message_cost
                   + (c.message_cost * c.markup_percent / 100.0))
                   * %(credit_factor)s AS credit_amount
            FROM billing_costoverride c, billing_account a, billing_tagpool t
            WHERE c.account_id = a.id
            AND a.account_number = %(account_number)s
            AND c.tag_pool_id = t.id
            AND t.name = %(tag_pool_name)s
            AND c.message_direction = %(message_direction)s
            LIMIT 1
            """

        params = {
            'credit_factor': app_settings.CREDIT_CONVERSION_FACTOR,
            'account_number': account_number,
            'tag_pool_name': tag_pool_name,
            'message_direction': message_direction
        }

        result = yield connection_pool.runQuery(query, params)
        if len(result) > 0:
            defer.returnValue(result[0])
        else:
            # Return the base cost
            query = """
                SELECT c.message_cost, c.markup_percent,
                       (c.message_cost
                       + (c.message_cost * c.markup_percent / 100.0))
                       * %(credit_factor)s AS credit_amount
                FROM billing_basecost c, billing_tagpool t
                WHERE c.tag_pool_id = t.id
                AND t.name = %(tag_pool_name)s
                AND c.message_direction = %(message_direction)s
                LIMIT 1
            """

            params = {
                'credit_factor': app_settings.CREDIT_CONVERSION_FACTOR,
                'tag_pool_name': tag_pool_name,
                'message_direction': message_direction
            }

            result = yield connection_pool.runQuery(query, params)
            if len(result) > 0:
                defer.returnValue(result[0])
            else:
                defer.returnValue(None)

    @defer.inlineCallbacks
    def get_transaction_list(self, account_number, page_number,
                             items_per_page):
        """Return a paginated list of transactions"""
        query = """
            SELECT id, account_number, tag_pool_name, message_direction,
                   message_cost, markup_percent, credit_factor,
                   credit_amount, status, created, last_modified
            FROM billing_transaction
            WHERE account_number = %(account_number)s
            ORDER BY created DESC
            OFFSET %(offset)s
            LIMIT %(limit)s
        """

        try:
            offset = int(page_number) * int(items_per_page)
        except ValueError:
            offset = 0
        try:
            limit = int(items_per_page)
        except ValueError:
            limit = 20
        params = {
            'account_number': account_number,
            'offset': offset,
            'limit': limit
        }

        result = yield connection_pool.runQuery(query, params)
        if len(result) > 0:
            defer.returnValue(result)
        else:
            defer.returnValue(None)

    @defer.inlineCallbacks
    def create_transaction_interaction(self, cursor, account_number,
                                       tag_pool_name, message_direction):
        """Create a new transaction for the given ``account_number``"""
        # Get the message cost
        result = yield self.get_cost(account_number, tag_pool_name,
                                     message_direction)

        message_cost = result.get('message_cost', 0)
        markup_percent = result.get('markup_percent', 0)
        credit_amount = result.get('credit_amount', 0)

        # Update the account's credit balance
        query = """
            UPDATE billing_account
            SET credit_balance = credit_balance - %(credit_amount)s
            WHERE account_number = %(account_number)s
        """

        params = {
            'credit_amount': credit_amount,
            'account_number': account_number
        }

        cursor = yield cursor.execute(query, params)

        # Create a new transaction
        query = """
            INSERT INTO billing_transaction
                (account_number, tag_pool_name, message_direction,
                 message_cost, markup_percent, credit_factor,
                 credit_amount, status, created, last_modified)
            VALUES
                (%(account_number)s, %(tag_pool_name)s, %(message_direction)s,
                 %(message_cost)s, %(markup_percent)s, %(credit_factor)s,
                 %(credit_amount)s, 'Completed', now(), now())
            RETURNING id, account_number, tag_pool_name, message_direction,
                      message_cost, markup_percent, credit_factor,
                      credit_amount, status, created, last_modified
        """

        params = {
            'account_number': account_number,
            'tag_pool_name': tag_pool_name,
            'message_direction': message_direction,
            'message_cost': message_cost,
            'markup_percent': markup_percent,
            'credit_factor': app_settings.CREDIT_CONVERSION_FACTOR,
            'credit_amount': -credit_amount
        }

        cursor = yield cursor.execute(query, params)
        transaction = yield cursor.fetchone()

        # Check the account's credit balance and raise an
        # alert if it has gone below the credit balance threshold
        query = """SELECT credit_balance, alert_credit_balance
                   FROM billing_account
                   WHERE account_number = %(account_number)s"""

        params = {'account_number': account_number}
        cursor = yield cursor.execute(query, params)
        result = yield cursor.fetchone()
        credit_balance = result.get('credit_balance')
        alert_credit_balance = result.get('alert_credit_balance')
        if credit_balance < alert_credit_balance and \
                credit_balance + credit_amount > alert_credit_balance:
            pass  # TODO: Raise a Low Credits alert; somehow

        defer.returnValue(transaction)

    @defer.inlineCallbacks
    def create_transaction(self, account_number, tag_pool_name,
                           message_direction):
        """Create a new transaction for the given ``account_number``"""
        result = yield connection_pool.runInteraction(
            self.create_transaction_interaction, account_number,
            tag_pool_name, message_direction)

        defer.returnValue(result)

root = Root()
root.putChild('accounts', AccountResource())
root.putChild('transactions', TransactionResource())
