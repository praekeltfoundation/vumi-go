import sys
import json
import decimal

from twisted.python import log
from twisted.internet import defer
from twisted.web.resource import Resource
from twisted.web.server import NOT_DONE_YET

from django.contrib.auth.hashers import make_password

from go.billing import settings as app_settings
from go.billing.utils import RealDictConnectionPool, JSONEncoder

log.startLogging(sys.stdout)

_connection_pool = None  # The txpostgres connection pool instance


def start_connection_pool():
    """Start the connection pool.

    If the connection pool has not yet been created or is closed create a
    new one and start it.

    """
    global _connection_pool
    if not _connection_pool or _connection_pool.closed:
        connection_string = app_settings.get_connection_string()
        min_connections = app_settings.API_MIN_CONNECTIONS
        _connection_pool = RealDictConnectionPool(None, connection_string,
                                                  min=min_connections)
        log.msg("Connecting to database %s..." % (connection_string,))
        return _connection_pool.start()
    return _connection_pool


def stop_connection_pool():
    """Close all connections in the connection pool"""
    if _connection_pool and not _connection_pool.closed:
        log.msg("Disconnecting from database...")
        _connection_pool.close()


def _handle_error(error, request, *args, **kwargs):
    """Log the error and return an HTTP 500 response"""
    log.err(error)
    request.setResponseCode(500)  # Internal Server Error
    request.write(error.getErrorMessage())
    request.finish()


def _render_to_json(result, request, *args, **kwargs):
    """Render the ``result`` as a JSON string.

    If the result is ``None`` return an HTTP 404 response.

    """
    if result is not None:
        request.setResponseCode(200)  # OK
        request.setHeader('Content-Type', 'application/json')
        request.write(json.dumps(result, cls=JSONEncoder))
    else:
        request.setResponseCode(404)  # Not Found
    request.finish()


def _parse_json(request):
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


class UserResource(Resource):
    """Expose a REST interface for a user"""

    isLeaf = True

    def render_GET(self, request):
        """Handle an HTTP GET request"""
        params = filter(None, request.postpath)
        if len(params) > 0:
            d = self.get_user(params[0])
            d.addCallbacks(_render_to_json, _handle_error,
                           callbackArgs=[request], errbackArgs=[request])

        else:
            d = self.get_user_list()
            d.addCallbacks(_render_to_json, _handle_error,
                           callbackArgs=[request], errbackArgs=[request])

        return NOT_DONE_YET

    @defer.inlineCallbacks
    def get_user(self, id):
        """Fetch the user with the given ``id``"""
        query = """
            SELECT id, email, first_name, last_name
            FROM auth_user
            WHERE id = %(id)s
        """

        params = {'id': id}
        result = yield _connection_pool.runQuery(query, params)
        if len(result) > 0:
            defer.returnValue(result[0])
        else:
            defer.returnValue(None)

    @defer.inlineCallbacks
    def get_user_list(self):
        """Fetch all users"""
        query = """
            SELECT id, email, first_name, last_name
            FROM auth_user
        """

        result = yield _connection_pool.runQuery(query)
        defer.returnValue(result)

    def render_POST(self, request):
        """Handle an HTTP POST request"""
        data = _parse_json(request)
        email = data.get('email', None)
        first_name = data.get('first_name', "")
        last_name = data.get('last_name', "")
        password = data.get('password', None)
        if email and password:
            d = self.create_user(email, first_name, last_name, password)
            d.addCallbacks(_render_to_json, _handle_error,
                           callbackArgs=[request], errbackArgs=[request])

            return NOT_DONE_YET
        else:
            request.setResponseCode(400)  # Bad Request

    @defer.inlineCallbacks
    def create_user_interaction(self, cursor, email, first_name, last_name,
                                password):
        """Create a new user"""
        query = """
            INSERT INTO auth_user
                (username, first_name, last_name, email, password,
                 is_staff, is_active, is_superuser, last_login, date_joined)
            VALUES
                (%(username)s, %(first_name)s, %(last_name)s, %(email)s,
                 %(password)s, FALSE, TRUE, FALSE, now(), now())
            RETURNING id, email, first_name, last_name
        """

        params = {
            'username': email,
            'first_name': first_name,
            'last_name': last_name,
            'email': email,
            'password': make_password(password)
        }

        cursor = yield cursor.execute(query, params)
        result = yield cursor.fetchone()
        defer.returnValue(result)

    @defer.inlineCallbacks
    def create_user(self, email, first_name, last_name, password):
        """Create a new user"""
        result = yield _connection_pool.runInteraction(
            self.create_user_interaction, email, first_name, last_name,
            password)

        defer.returnValue(result)


class AccountResource(Resource):
    """Expose a REST interface for an account"""

    isLeaf = True

    def render_GET(self, request):
        """Handle an HTTP GET request"""
        params = filter(None, request.postpath)
        if len(params) > 0:
            d = self.get_account(params[0])
            d.addCallbacks(_render_to_json, _handle_error,
                           callbackArgs=[request], errbackArgs=[request])

        else:
            d = self.get_account_list()
            d.addCallbacks(_render_to_json, _handle_error,
                           callbackArgs=[request], errbackArgs=[request])

        return NOT_DONE_YET

    @defer.inlineCallbacks
    def get_account(self, account_number):
        """Fetch the account with the given ``account_number``"""
        query = """
            SELECT u.email, a.account_number, a.description,
                   a.credit_balance, a.alert_threshold,
                   a.alert_credit_balance
            FROM billing_account a, auth_user u
            WHERE a.user_id = u.id
            AND a.account_number = %(account_number)s
        """

        params = {'account_number': account_number}
        result = yield _connection_pool.runQuery(query, params)
        if len(result) > 0:
            defer.returnValue(result[0])
        else:
            defer.returnValue(None)

    @defer.inlineCallbacks
    def get_account_list(self):
        """Fetch all accounts"""
        query = """
            SELECT u.email, a.account_number, a.description,
                   a.credit_balance, a.alert_threshold,
                   a.alert_credit_balance
            FROM billing_account a, auth_user u
            WHERE a.user_id = u.id
        """

        result = yield _connection_pool.runQuery(query)
        defer.returnValue(result)

    def render_POST(self, request):
        """Handle an HTTP POST request"""
        params = filter(None, request.postpath)
        if len(params) == 0:
            data = _parse_json(request)
            email = data.get('email', None)
            account_number = data.get('account_number', None)
            description = data.get('description', "")
            if email and account_number:
                d = self.create_account(email, account_number, description)
                d.addCallbacks(_render_to_json, _handle_error,
                               callbackArgs=[request], errbackArgs=[request])

                return NOT_DONE_YET
            else:
                request.setResponseCode(400)  # Bad Request
        elif len(params) == 2:
            (account_number, path), rest = params[:2], params[2:]
            if path == 'credits':
                data = _parse_json(request)
                d = self.load_credits(account_number,
                                      data.get('credit_amount', 0))

                d.addCallbacks(_render_to_json, _handle_error,
                               callbackArgs=[request], errbackArgs=[request])

                return NOT_DONE_YET
            else:
                request.setResponseCode(400)  # Bad Request
        else:
            request.setResponseCode(400)  # Bad Request
        return ''

    @defer.inlineCallbacks
    def create_account_interaction(self, cursor, email, account_number,
                                   description):
        """Create a new account"""
        # Find the user with the given email
        query = """SELECT id
                   FROM auth_user
                   WHERE email = %(email)s"""

        params = {'email': email}
        cursor = yield cursor.execute(query, params)
        result = yield cursor.fetchone()

        # Create a new account
        query = """
            INSERT INTO billing_account
                (user_id, account_number, description, credit_balance,
                 alert_threshold, alert_credit_balance)
            VALUES
                (%(user_id)s, %(account_number)s, %(description)s, 0, 0.0, 0)
            RETURNING id
        """

        params = {
            'user_id': result.get('id'),
            'account_number': account_number,
            'description': description
        }

        cursor = yield cursor.execute(query, params)
        result = yield cursor.fetchone()

        # Fetch the newly created account
        query = """
            SELECT u.email, a.account_number, a.description,
                   a.credit_balance, a.alert_threshold,
                   a.alert_credit_balance
            FROM billing_account a, auth_user u
            WHERE a.user_id = u.id
            AND a.id = %(id)s
        """

        params = {'id': result.get('id')}
        cursor = yield cursor.execute(query, params)
        result = yield cursor.fetchone()
        defer.returnValue(result)

    @defer.inlineCallbacks
    def create_account(self, email, account_number, description):
        """Create a new account"""
        result = yield _connection_pool.runInteraction(
            self.create_account_interaction, email, account_number,
            description)

        defer.returnValue(result)

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
        result = yield _connection_pool.runInteraction(
            self.load_credits_interaction, account_number, credit_amount)

        defer.returnValue(result)


class CostResource(Resource):
    """Expose a REST interface for a message cost"""

    isLeaf = True

    def render_GET(self, request):
        """Handle an HTTP GET request"""
        account_number = request.args.get('account_number', [None])
        tag_pool_name = request.args.get('tag_pool_name', [None])
        message_direction = request.args.get('message_direction', [None])
        d = self.get_cost_list(account_number[0], tag_pool_name[0],
                               message_direction[0])

        d.addCallbacks(_render_to_json, _handle_error,
                       callbackArgs=[request], errbackArgs=[request])

        return NOT_DONE_YET

    def render_POST(self, request):
        """Handle an HTTP POST request"""
        data = _parse_json(request)
        account_number = data.get('account_number', None)
        tag_pool_name = data.get('tag_pool_name', None)
        message_direction = data.get('message_direction', None)
        message_cost = data.get('message_cost', None)
        markup_percent = data.get('markup_percent', None)
        if tag_pool_name and message_direction and message_cost \
                and markup_percent:
            d = self.create_cost(account_number, tag_pool_name,
                                 message_direction, message_cost,
                                 markup_percent)

            d.addCallbacks(_render_to_json, _handle_error,
                           callbackArgs=[request], errbackArgs=[request])

            return NOT_DONE_YET
        else:
            request.setResponseCode(400)  # Bad Request
            return ''

    @defer.inlineCallbacks
    def get_cost_list(self, account_number, tag_pool_name,
                      message_direction):
        """Fetch all message costs for the given parameters.

        If an ``account_number`` is given, first check for an account cost
        override.

        """
        if account_number:
            query = """
                SELECT a.account_number, t.name AS tag_pool_name,
                       c.message_direction, c.message_cost, c.markup_percent,
                       (c.message_cost
                        + (c.message_cost * c.markup_percent / 100.0))
                        * %(credit_factor)s AS credit_amount
                FROM billing_costoverride c, billing_account a,
                     billing_tagpool t
                WHERE c.account_id = a.id
                AND c.tag_pool_id = t.id
                AND a.account_number = %(account_number)s
            """

            params = {
                'credit_factor': app_settings.CREDIT_CONVERSION_FACTOR,
                'account_number': account_number
            }

            if tag_pool_name:
                query += " AND t.name = %(tag_pool_name)s"
                params['tag_pool_name'] = tag_pool_name
            if message_direction:
                query += " AND c.message_direction = %(message_direction)s"
                params['message_direction'] = message_direction

            result = yield _connection_pool.runQuery(query, params)
        else:
            result = None

        if result:
            defer.returnValue(result)
        else:
            query = """
                SELECT t.name AS tag_pool_name, c.message_direction,
                       c.message_cost, c.markup_percent,
                       (c.message_cost
                        + (c.message_cost * c.markup_percent / 100.0))
                        * %(credit_factor)s AS credit_amount
                FROM billing_basecost c, billing_tagpool t
                WHERE c.tag_pool_id = t.id
            """

            params = {
                'credit_factor': app_settings.CREDIT_CONVERSION_FACTOR,
            }

            if tag_pool_name:
                query += " AND t.name = %(tag_pool_name)s"
                params['tag_pool_name'] = tag_pool_name
            if message_direction:
                query += " AND c.message_direction = %(message_direction)s"
                params['message_direction'] = message_direction

            result = yield _connection_pool.runQuery(query, params)
            defer.returnValue(result)

    @defer.inlineCallbacks
    def create_cost_interaction(self, cursor, account_number, tag_pool_name,
                                message_direction, message_cost,
                                markup_percent):
        """Create a new cost.

        If an ``account_number`` is given create a message cost override,
        otherwise create a base message cost.

        """
        # Get the tag pool or create a new one if it doesn't exist
        query = """
            WITH new_row AS (
                INSERT INTO billing_tagpool (name, description)
                SELECT %(tag_pool_name)s, ''
                WHERE NOT EXISTS (SELECT * FROM billing_tagpool
                                  WHERE name = %(tag_pool_name)s)
                RETURNING id, name, description
            )
            SELECT id, name, description FROM new_row
            UNION
            SELECT id, name, description
            FROM billing_tagpool
            WHERE name = %(tag_pool_name)s
        """

        params = {'tag_pool_name': tag_pool_name}
        cursor = yield cursor.execute(query, params)
        tag_pool = yield cursor.fetchone()

        if account_number:  # Create a message cost override
            query = """
                INSERT INTO billing_costoverride
                    (account_id, tag_pool_id, message_direction,
                     message_cost, markup_percent)
                VALUES
                    ((SELECT id FROM billing_account
                      WHERE account_number = %(account_number)s),
                     %(tag_pool_id)s, %(message_direction)s,
                     %(message_cost)s, %(markup_percent)s)
                RETURNING
                    %(account_number)s AS account_number,
                    %(tag_pool_name)s AS tag_pool_name,
                    message_direction, message_cost, markup_percent,
                    (message_cost + (message_cost * markup_percent / 100.0))
                     * %(credit_factor)s AS credit_amount
            """

            params = {
                'account_number': account_number,
                'tag_pool_id': tag_pool.get('id'),
                'tag_pool_name': tag_pool_name,
                'message_direction': message_direction,
                'message_cost': message_cost,
                'markup_percent': markup_percent,
                'credit_factor': app_settings.CREDIT_CONVERSION_FACTOR
            }

            cursor = yield cursor.execute(query, params)
            result = yield cursor.fetchone()
            defer.returnValue(result)
        else:  # Create the base message cost
            query = """
                INSERT INTO billing_basecost
                    (tag_pool_id, message_direction, message_cost,
                     markup_percent)
                VALUES
                    (%(tag_pool_id)s, %(message_direction)s,
                     %(message_cost)s, %(markup_percent)s)
                RETURNING
                    %(tag_pool_name)s AS tag_pool_name,
                    message_direction, message_cost, markup_percent,
                    (message_cost + (message_cost * markup_percent / 100.0))
                     * %(credit_factor)s AS credit_amount
            """

            params = {
                'tag_pool_id': tag_pool.get('id'),
                'tag_pool_name': tag_pool_name,
                'message_direction': message_direction,
                'message_cost': message_cost,
                'markup_percent': markup_percent,
                'credit_factor': app_settings.CREDIT_CONVERSION_FACTOR
            }

            cursor = yield cursor.execute(query, params)
            result = yield cursor.fetchone()
            defer.returnValue(result)

    @defer.inlineCallbacks
    def create_cost(self, account_number, tag_pool_name, message_direction,
                    message_cost, markup_percent):
        """Create a new cost.

        If an ``account_number`` is given create a message cost override,
        otherwise create a base message cost.

        """
        result = yield _connection_pool.runInteraction(
            self.create_cost_interaction, account_number,
            tag_pool_name, message_direction, message_cost, markup_percent)

        defer.returnValue(result)


class TransactionResource(Resource):
    """Expose a REST interface for a transaction"""

    isLeaf = True

    def render_GET(self, request):
        """Handle an HTTP GET request"""
        account_number = request.args.get('account_number', [])
        page_number = request.args.get('page_number', [0])
        items_per_page = request.args.get('items_per_page', [20])
        if len(account_number) > 0:
            d = self.get_transaction_list(
                account_number[0], page_number[0], items_per_page[0])

            d.addCallbacks(_render_to_json, _handle_error,
                           callbackArgs=[request], errbackArgs=[request])

        else:
            request.setResponseCode(400)  # Bad Request
            return ''
        return NOT_DONE_YET

    def render_POST(self, request):
        """Handle an HTTP POST request"""
        data = _parse_json(request)
        account_number = data.get('account_number', None)
        tag_pool_name = data.get('tag_pool_name', None)
        message_direction = data.get('message_direction', None)
        if account_number and tag_pool_name and message_direction:
            d = self.create_transaction(
                account_number, tag_pool_name, message_direction)

            d.addCallbacks(_render_to_json, _handle_error,
                           callbackArgs=[request], errbackArgs=[request])

            return NOT_DONE_YET
        else:
            request.setResponseCode(400)  # Bad Request
            return ''

    @defer.inlineCallbacks
    def get_cost(self, account_number, tag_pool_name, message_direction):
        """Return the message cost.

        First check if there is a cost override for the given
        ``account_number``. If not, return the base cost.

        """
        # Check for an account cost override
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

        result = yield _connection_pool.runQuery(query, params)
        if len(result) > 0:
            defer.returnValue(result[0])
        else:
            # Find the message base cost
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

            result = yield _connection_pool.runQuery(query, params)
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

        result = yield _connection_pool.runQuery(query, params)
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
        result = yield _connection_pool.runInteraction(
            self.create_transaction_interaction, account_number,
            tag_pool_name, message_direction)

        defer.returnValue(result)

root = Root()
root.putChild('users', UserResource())
root.putChild('accounts', AccountResource())
root.putChild('costs', CostResource())
root.putChild('transactions', TransactionResource())
