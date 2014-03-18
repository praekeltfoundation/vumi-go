import json

from twisted.python import log
from twisted.internet import defer
from twisted.web.resource import Resource
from twisted.web.server import NOT_DONE_YET

from django.contrib.auth.hashers import make_password

from go.billing import settings as app_settings
from go.billing.models import MessageCost
from go.billing.utils import JSONEncoder, JSONDecoder, BillingError


class BaseResource(Resource):
    """Base class for the APIs ``Resource``s"""

    _connection_pool = None  # The txpostgres connection pool

    def __init__(self, connection_pool):
        Resource.__init__(self)
        self._connection_pool = connection_pool
        self._auth_user_table = app_settings.get_user_table()

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


class UserResource(BaseResource):
    """Expose a REST interface for a user"""

    isLeaf = True

    def render_GET(self, request):
        """Handle an HTTP GET request"""
        params = filter(None, request.postpath)
        if len(params) > 0:
            d = self.get_user(params[0])
            d.addCallbacks(self._render_to_json, self._handle_error,
                           callbackArgs=[request], errbackArgs=[request])

        else:
            d = self.get_user_list()
            d.addCallbacks(self._render_to_json, self._handle_error,
                           callbackArgs=[request], errbackArgs=[request])

        return NOT_DONE_YET

    @defer.inlineCallbacks
    def get_user(self, id):
        """Fetch the user with the given ``id``"""
        query = """
            SELECT id, email, first_name, last_name
            FROM %s
            WHERE id = %%(id)s
        """ % self._auth_user_table

        params = {'id': id}
        result = yield self._connection_pool.runQuery(query, params)
        if len(result) > 0:
            defer.returnValue(result[0])
        else:
            defer.returnValue(None)

    @defer.inlineCallbacks
    def get_user_list(self):
        """Fetch all users"""
        query = """
            SELECT id, email, first_name, last_name
            FROM %s
        """ % self._auth_user_table

        result = yield self._connection_pool.runQuery(query)
        defer.returnValue(result)

    def render_POST(self, request):
        """Handle an HTTP POST request"""
        data = self._parse_json(request)
        if data:
            email = data.get('email', None)
            first_name = data.get('first_name', "")
            last_name = data.get('last_name', "")
            password = data.get('password', None)
            if email and password:
                d = self.create_user(email, first_name, last_name, password)
                d.addCallbacks(self._render_to_json, self._handle_error,
                               callbackArgs=[request], errbackArgs=[request])

            else:
                self._handle_bad_request(request)
        else:
            self._handle_bad_request(request)
        return NOT_DONE_YET

    @defer.inlineCallbacks
    def create_user_interaction(self, cursor, email, first_name, last_name,
                                password):
        """Create a new user"""
        query = """
            INSERT INTO %s
                (email, first_name, last_name, password,
                 is_staff, is_active, is_superuser, last_login, date_joined)
            VALUES
                (%%(email)s, %%(first_name)s, %%(last_name)s,
                 %%(password)s, FALSE, TRUE, FALSE, now(), now())
            RETURNING id, email, first_name, last_name
        """ % self._auth_user_table

        params = {
            'email': email,
            'first_name': first_name,
            'last_name': last_name,
            'password': make_password(password)
        }

        cursor = yield cursor.execute(query, params)
        result = yield cursor.fetchone()
        defer.returnValue(result)

    @defer.inlineCallbacks
    def create_user(self, email, first_name, last_name, password):
        """Create a new user"""
        result = yield self._connection_pool.runInteraction(
            self.create_user_interaction, email, first_name, last_name,
            password)

        defer.returnValue(result)


class AccountResource(BaseResource):
    """Expose a REST interface for an account"""

    isLeaf = True

    def render_GET(self, request):
        """Handle an HTTP GET request"""
        params = filter(None, request.postpath)
        if len(params) > 0:
            d = self.get_account(params[0])
            d.addCallbacks(self._render_to_json, self._handle_error,
                           callbackArgs=[request], errbackArgs=[request])

        else:
            d = self.get_account_list()
            d.addCallbacks(self._render_to_json, self._handle_error,
                           callbackArgs=[request], errbackArgs=[request])

        return NOT_DONE_YET

    @defer.inlineCallbacks
    def get_account(self, account_number):
        """Fetch the account with the given ``account_number``"""
        query = """
            SELECT u.email, a.account_number, a.description,
                   a.credit_balance, a.alert_threshold,
                   a.alert_credit_balance
            FROM billing_account a, %s u
            WHERE a.user_id = u.id
            AND a.account_number = %%(account_number)s
        """ % self._auth_user_table

        params = {'account_number': account_number}
        result = yield self._connection_pool.runQuery(query, params)
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
            FROM billing_account a, %s u
            WHERE a.user_id = u.id
        """ % self._auth_user_table

        result = yield self._connection_pool.runQuery(query)
        defer.returnValue(result)

    def render_POST(self, request):
        """Handle an HTTP POST request"""
        params = filter(None, request.postpath)
        data = self._parse_json(request)
        if len(params) == 0 and data is not None:
            email = data.get('email', None)
            account_number = data.get('account_number', None)
            description = data.get('description', "")
            if email and account_number:
                d = self.create_account(email, account_number, description)
                d.addCallbacks(self._render_to_json, self._handle_error,
                               callbackArgs=[request], errbackArgs=[request])

            else:
                self._handle_bad_request(request)
        elif len(params) == 2 and data is not None:
            (account_number, path), rest = params[:2], params[2:]
            if path == 'credits':
                d = self.load_credits(account_number,
                                      data.get('credit_amount', 0))

                d.addCallbacks(self._render_to_json, self._handle_error,
                               callbackArgs=[request], errbackArgs=[request])

            else:
                self._handle_bad_request(request)
        else:
            self._handle_bad_request(request)
        return NOT_DONE_YET

    @defer.inlineCallbacks
    def create_account_interaction(self, cursor, email, account_number,
                                   description):
        """Create a new account"""
        # Find the user with the given email
        query = """
            SELECT id
            FROM %s
            WHERE email = %%(email)s
        """ % self._auth_user_table

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
            FROM billing_account a, %s u
            WHERE a.user_id = u.id
            AND a.id = %%(id)s
        """ % self._auth_user_table

        params = {'id': result.get('id')}
        cursor = yield cursor.execute(query, params)
        result = yield cursor.fetchone()
        defer.returnValue(result)

    @defer.inlineCallbacks
    def create_account(self, email, account_number, description):
        """Create a new account"""
        result = yield self._connection_pool.runInteraction(
            self.create_account_interaction, email, account_number,
            description)

        defer.returnValue(result)

    @defer.inlineCallbacks
    def load_credits_interaction(self, cursor, account_number, credit_amount):
        # Create a new transaction
        query = """INSERT INTO billing_transaction
                       (account_number, tag_pool_name, tag_name,
                        message_direction, credit_amount, status,
                        created, last_modified)
                   VALUES (%(account_number)s, '', '', '', %(credit_amount)s,
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
        result = yield self._connection_pool.runInteraction(
            self.load_credits_interaction, account_number, credit_amount)

        defer.returnValue(result)


class CostResource(BaseResource):
    """Expose a REST interface for a message cost"""

    isLeaf = True

    def render_GET(self, request):
        """Handle an HTTP GET request"""
        account_number = request.args.get('account_number', [None])
        tag_pool_name = request.args.get('tag_pool_name', [None])
        message_direction = request.args.get('message_direction', [None])
        d = self.get_cost_list(account_number[0], tag_pool_name[0],
                               message_direction[0])

        d.addCallbacks(self._render_to_json, self._handle_error,
                       callbackArgs=[request], errbackArgs=[request])

        return NOT_DONE_YET

    def render_POST(self, request):
        """Handle an HTTP POST request"""
        data = self._parse_json(request)
        if data:
            account_number = data.get('account_number', None)
            tag_pool_name = data.get('tag_pool_name', None)
            message_direction = data.get('message_direction', None)
            message_cost = data.get('message_cost', None)
            session_cost = data.get('session_cost', None)
            markup_percent = data.get('markup_percent', None)
            if all((message_direction, message_cost, session_cost,
                    markup_percent, tag_pool_name or not account_number)):
                d = self.create_cost(account_number, tag_pool_name,
                                     message_direction, message_cost,
                                     session_cost, markup_percent)

                d.addCallbacks(self._render_to_json, self._handle_error,
                               callbackArgs=[request], errbackArgs=[request])

            else:
                self._handle_bad_request(request)
        else:
            self._handle_bad_request(request)
        return NOT_DONE_YET

    @defer.inlineCallbacks
    def get_cost_list(self, account_number, tag_pool_name,
                      message_direction):
        """Fetch all message costs for the given parameters.

        If an ``account_number`` is given, first check for an account cost
        override.

        """
        query = """
            SELECT a.account_number, t.name AS tag_pool_name,
                   c.message_direction, c.message_cost,
                   c.session_cost, c.markup_percent
            FROM billing_messagecost c
                 LEFT OUTER JOIN billing_tagpool t ON (c.tag_pool_id = t.id)
                 LEFT OUTER JOIN billing_account a ON (c.account_id = a.id)
        """

        # Construct the query conditions dynamically based on the sent
        # parameters
        conditions = ""
        params = {}
        if account_number:
            if conditions:
                conditions += " AND "
            else:
                conditions += " WHERE "
            conditions += "a.account_number = %(account_number)s"
            params['account_number'] = account_number
        if tag_pool_name:
            if conditions:
                conditions += " AND "
            else:
                conditions += " WHERE "
            conditions += "t.name = %(tag_pool_name)s"
            params['tag_pool_name'] = tag_pool_name
        if message_direction:
            if conditions:
                conditions += " AND "
            else:
                conditions += " WHERE "
            conditions += "c.message_direction = %(message_direction)s"
            params['message_direction'] = message_direction
        query += conditions
        query += " ORDER BY a.account_number, t.name, c.message_direction"
        result = yield self._connection_pool.runQuery(query, params)

        defer.returnValue(result)

    @defer.inlineCallbacks
    def create_cost_interaction(self, cursor, account_number, tag_pool_name,
                                message_direction, message_cost,
                                session_cost, markup_percent):
        """Create a new cost.

        If an ``account_number`` is supplied assume that there is a valid
        account entry in the database.

        """
        # Get the tag pool or create a new one if it doesn't exist
        query = """
            WITH new_row AS (
                INSERT INTO billing_tagpool (name, description)
                SELECT %(tag_pool_name)s, ''
                WHERE NOT EXISTS (SELECT * FROM billing_tagpool
                                  WHERE name = %(tag_pool_name)s)
                RETURNING id, name, description)
            SELECT id, name, description FROM new_row
            UNION
            SELECT id, name, description
            FROM billing_tagpool
            WHERE name = %(tag_pool_name)s
        """

        if tag_pool_name is not None:
            params = {'tag_pool_name': tag_pool_name}
            cursor = yield cursor.execute(query, params)
            tag_pool = yield cursor.fetchone()
        else:
            tag_pool = {'id': None}

        if account_number:
            query = """
                INSERT INTO billing_messagecost
                    (account_id, tag_pool_id, message_direction,
                     message_cost, session_cost, markup_percent)
                VALUES
                    ((SELECT id FROM billing_account
                      WHERE account_number = %(account_number)s),
                     %(tag_pool_id)s, %(message_direction)s,
                     %(message_cost)s, %(session_cost)s,
                     %(markup_percent)s)
                RETURNING
                    %(account_number)s AS account_number,
                    %(tag_pool_name)s AS tag_pool_name,
                    message_direction, message_cost,
                    session_cost, markup_percent
            """

            params = {
                'account_number': account_number,
                'tag_pool_id': tag_pool.get('id'),
                'tag_pool_name': tag_pool_name,
                'message_direction': message_direction,
                'message_cost': message_cost,
                'session_cost': session_cost,
                'markup_percent': markup_percent
            }
        else:
            query = """
                INSERT INTO billing_messagecost
                    (account_id, tag_pool_id, message_direction,
                     message_cost, session_cost, markup_percent)
                VALUES
                    (NULL, %(tag_pool_id)s, %(message_direction)s,
                     %(message_cost)s, %(session_cost)s, %(markup_percent)s)
                RETURNING
                    NULL AS account_number,
                    %(tag_pool_name)s AS tag_pool_name,
                    message_direction, message_cost, session_cost,
                    markup_percent
            """

            params = {
                'tag_pool_id': tag_pool.get('id'),
                'tag_pool_name': tag_pool_name,
                'message_direction': message_direction,
                'message_cost': message_cost,
                'session_cost': session_cost,
                'markup_percent': markup_percent
            }

        cursor = yield cursor.execute(query, params)
        result = yield cursor.fetchone()

        defer.returnValue(result)

    @defer.inlineCallbacks
    def create_cost(self, account_number, tag_pool_name, message_direction,
                    message_cost, session_cost, markup_percent):
        """Create a new cost.

        If an ``account_number`` is given create a message cost override,
        otherwise create a base message cost.

        """
        result = yield self._connection_pool.runInteraction(
            self.create_cost_interaction, account_number,
            tag_pool_name, message_direction, message_cost, session_cost,
            markup_percent)

        defer.returnValue(result)


class TransactionResource(BaseResource):
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

            d.addCallbacks(self._render_to_json, self._handle_error,
                           callbackArgs=[request], errbackArgs=[request])

        else:
            self._handle_bad_request(request)
        return NOT_DONE_YET

    def render_POST(self, request):
        """Handle an HTTP POST request"""
        data = self._parse_json(request)
        if data:
            account_number = data.get('account_number', None)
            message_id = data.get('message_id', None)
            tag_pool_name = data.get('tag_pool_name', None)
            tag_name = data.get('tag_name', None)
            message_direction = data.get('message_direction', None)
            session_created = data.get('session_created', None)
            if all((account_number, message_id, tag_pool_name, tag_name,
                    message_direction, session_created is not None)):
                d = self.create_transaction(
                    account_number, message_id, tag_pool_name, tag_name,
                    message_direction, session_created)

                d.addCallbacks(self._render_to_json, self._handle_error,
                               callbackArgs=[request], errbackArgs=[request])
            else:
                self._handle_bad_request(request)
        else:
            self._handle_bad_request(request)
        return NOT_DONE_YET

    @defer.inlineCallbacks
    def get_cost(self, account_number, tag_pool_name, message_direction,
                 session_created):
        """Return the message cost"""
        query = """
            SELECT t.account_number, t.tag_pool_name, t.message_direction,
                   t.message_cost, t.session_cost, t.markup_percent
            FROM (SELECT a.account_number, t.name AS tag_pool_name,
                         c.message_direction, c.message_cost,
                         c.session_cost, c.markup_percent
                  FROM billing_messagecost c
                  INNER JOIN billing_tagpool t ON (c.tag_pool_id = t.id)
                  INNER JOIN billing_account a ON (c.account_id = a.id)
                  WHERE a.account_number = %(account_number)s
                  AND t.name = %(tag_pool_name)s
                  AND c.message_direction = %(message_direction)s
                  UNION
                  SELECT NULL AS account_number, t.name AS tag_pool_name,
                         c.message_direction, c.message_cost,
                         c.session_cost, c.markup_percent
                  FROM billing_messagecost c
                  INNER JOIN billing_tagpool t ON (c.tag_pool_id = t.id)
                  WHERE c.account_id IS NULL
                  AND t.name = %(tag_pool_name)s
                  AND c.message_direction = %(message_direction)s
                  UNION
                  SELECT NULL AS account_number, NULL AS tag_pool_name,
                         c.message_direction, c.message_cost,
                         c.session_cost, c.markup_percent
                  FROM billing_messagecost c
                  WHERE c.account_id IS NULL
                  AND c.tag_pool_id IS NULL
                  AND c.message_direction = %(message_direction)s
            ) as t
            ORDER BY t.account_number
            LIMIT 1
            """

        params = {
            'account_number': account_number,
            'tag_pool_name': tag_pool_name,
            'message_direction': message_direction
        }

        result = yield self._connection_pool.runQuery(query, params)
        if len(result) > 0:
            message_cost = result[0]
            message_cost['credit_amount'] = MessageCost.calculate_credit_cost(
                message_cost['message_cost'],
                message_cost['markup_percent'],
                message_cost['session_cost'],
                session_created=session_created)

            defer.returnValue(message_cost)
        else:
            defer.returnValue(None)

    @defer.inlineCallbacks
    def get_transaction_list(self, account_number, page_number,
                             items_per_page):
        """Return a paginated list of transactions"""
        query = """
            SELECT id, account_number, message_id,
                   tag_pool_name, tag_name,
                   message_direction, message_cost,
                   session_created, session_cost,
                   markup_percent, credit_factor, credit_amount,
                   status, created, last_modified
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
        except TypeError:
            offset = 0
        try:
            limit = int(items_per_page)
        except ValueError:
            limit = 20
        except TypeError:
            limit = 20
        params = {
            'account_number': account_number,
            'offset': offset,
            'limit': limit
        }

        result = yield self._connection_pool.runQuery(query, params)
        if len(result) > 0:
            defer.returnValue(result)
        else:
            defer.returnValue(None)

    @defer.inlineCallbacks
    def create_transaction_interaction(self, cursor, account_number,
                                       message_id, tag_pool_name, tag_name,
                                       message_direction, session_created):
        """Create a new transaction for the given ``account_number``"""
        # Get the message cost
        result = yield self.get_cost(account_number, tag_pool_name,
                                     message_direction, session_created)

        if result is None:
            raise BillingError(
                "Unable to determine %s message cost for account %s"
                " and tag pool %s" % (
                    message_direction, account_number, tag_pool_name))

        message_cost = result.get('message_cost', 0)
        session_cost = result.get('session_cost', 0)
        markup_percent = result.get('markup_percent', 0)
        credit_amount = result.get('credit_amount', 0)

        # Create a new transaction
        query = """
            INSERT INTO billing_transaction
                (account_number, message_id,
                 tag_pool_name, tag_name,
                 message_direction, message_cost,
                 session_created, session_cost,
                 markup_percent, credit_factor,
                 credit_amount, status, created, last_modified)
            VALUES
                (%(account_number)s, %(message_id)s,
                 %(tag_pool_name)s, %(tag_name)s,
                 %(message_direction)s, %(message_cost)s,
                 %(session_created)s, %(session_cost)s,
                 %(markup_percent)s, %(credit_factor)s,
                 %(credit_amount)s, 'Completed', now(),
                 now())
            RETURNING id, account_number, message_id,
                      tag_pool_name, tag_name,
                      message_direction, message_cost,
                      session_cost, session_created,
                      markup_percent, credit_factor, credit_amount, status,
                      created, last_modified
        """

        params = {
            'account_number': account_number,
            'message_id': message_id,
            'tag_pool_name': tag_pool_name,
            'tag_name': tag_name,
            'message_direction': message_direction,
            'message_cost': message_cost,
            'session_created': session_created,
            'session_cost': session_cost,
            'markup_percent': markup_percent,
            'credit_factor': app_settings.CREDIT_CONVERSION_FACTOR,
            'credit_amount': -credit_amount
        }

        cursor = yield cursor.execute(query, params)
        transaction = yield cursor.fetchone()

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

        # Check the account's credit balance and raise an
        # alert if it has gone below the credit balance threshold
        query = """SELECT credit_balance, alert_credit_balance
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

        credit_balance = result.get('credit_balance')
        alert_credit_balance = result.get('alert_credit_balance')
        if (credit_balance < alert_credit_balance and
                credit_balance + credit_amount > alert_credit_balance):
            pass  # TODO: Raise a Low Credits alert; somehow

        defer.returnValue(transaction)

    @defer.inlineCallbacks
    def create_transaction(self, account_number, message_id, tag_pool_name,
                           tag_name, message_direction, session_created):
        """Create a new transaction for the given ``account_number``"""
        result = yield self._connection_pool.runInteraction(
            self.create_transaction_interaction, account_number, message_id,
            tag_pool_name, tag_name, message_direction, session_created)

        defer.returnValue(result)


class Root(BaseResource):
    """The root resource"""

    def __init__(self, connection_pool):
        BaseResource.__init__(self, connection_pool)
        self.putChild('users', UserResource(connection_pool))
        self.putChild('accounts', AccountResource(connection_pool))
        self.putChild('costs', CostResource(connection_pool))
        self.putChild('transactions', TransactionResource(connection_pool))

    def getChild(self, name, request):
        if name == '':
            return self
        return Resource.getChild(self, name, request)

    def render_GET(self, request):
        request.setResponseCode(200)  # OK
        return ''
