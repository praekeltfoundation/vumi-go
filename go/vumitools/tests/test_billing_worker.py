import json
import decimal

from twisted.internet.defer import inlineCallbacks, returnValue
from twisted.web.client import Agent, Request, Response

from vumi.tests.helpers import VumiTestCase
from vumi.utils import mkheaders, StringProducer

from go.vumitools import billing_worker
from go.vumitools.billing_worker import BillingApi, BillingDispatcher
from go.vumitools.tests.helpers import VumiApiHelper, GoMessageHelper
from go.vumitools.utils import MessageMetadataHelper

from go.billing.api import BillingError
from go.billing.utils import JSONEncoder


class BillingApiMock(object):

    def __init__(self):
        self.transactions = []

    def _record(self, items, vars):
        del vars["self"]
        items.append(vars)

    def create_transaction(self, account_number, tag_pool_name,
                           tag_name, message_direction, session_created):
        self._record(self.transactions, locals())
        return {
            "id": 1,
            "account_number": account_number,
            "tag_pool_name": tag_pool_name,
            "tag_name": tag_name,
            "message_direction": message_direction,
            "message_cost": 80,
            "session_created": session_created,
            "session_cost": 30,
            "markup_percent": decimal.Decimal('10.0'),
            "credit_amount": -35,
            "credit_factor": decimal.Decimal('0.4'),
            "created": "2013-10-30T10:42:51.144745+02:00",
            "last_modified": "2013-10-30T10:42:51.144745+02:00",
            "status": "Completed"
        }


class HttpRequestMock(object):

    def __init__(self, response=None):
        self.request = None
        self.response = response

    def _mk_request(self, uri, method='POST', headers={}, data=None):
        return Request(method, uri, mkheaders(headers),
                       StringProducer(data) if data else None)

    def dummy_http_request_full(self, url, data=None, headers={},
                                method='POST', timeout=None,
                                data_limit=None, context_factory=None,
                                agent_class=Agent):
        self.request = self._mk_request(url, method, headers, data)
        return self.response


class TestBillingApi(VumiTestCase):

    @inlineCallbacks
    def setUp(self):
        yield super(TestBillingApi, self).setUp()
        self.api_url = "http://localhost:9090/"
        self.billing_api = BillingApi(self.api_url)

    def _mk_response(self, code=200, phrase='OK', headers={},
                     delivered_body='{}'):
        response = Response(('HTTP', 1, 1), code, phrase,
                            mkheaders(headers), None)

        response.delivered_body = delivered_body
        return response

    @inlineCallbacks
    def test_create_transaction_request(self):
        hrm = HttpRequestMock(self._mk_response())
        self.patch(billing_worker, 'http_request_full',
                   hrm.dummy_http_request_full)

        kwargs = {
            'account_number': "test-account",
            'tag_pool_name': "pool1",
            'tag_name': "1234",
            'message_direction': "Inbound",
            'session_created': False,
        }
        yield self.billing_api.create_transaction(**kwargs)
        self.assertEqual(hrm.request.uri, "%stransactions" % (self.api_url,))
        self.assertEqual(hrm.request.bodyProducer.body,
                         json.dumps(kwargs, cls=JSONEncoder))

    @inlineCallbacks
    def test_create_transaction_response(self):
        delivered_body = {
            "id": 1,
            "account_number": "test-account",
            "tag_pool_name": "pool1",
            "tag_name": "1234",
            "message_direction": "Inbound",
            "message_cost": 80,
            "session_created": False,
            "session_cost": 30,
            "markup_percent": decimal.Decimal('10.0'),
            "credit_amount": -35,
            "credit_factor": decimal.Decimal('0.4'),
            "created": "2013-10-30T10:42:51.144745+02:00",
            "last_modified": "2013-10-30T10:42:51.144745+02:00",
            "status": "Completed"
        }
        response = self._mk_response(
            delivered_body=json.dumps(delivered_body, cls=JSONEncoder))

        hrm = HttpRequestMock(response)
        self.patch(billing_worker, 'http_request_full',
                   hrm.dummy_http_request_full)

        kwargs = {
            'account_number': "test-account",
            'tag_pool_name': "pool1",
            'tag_name': "1234",
            'message_direction': "Inbound",
            'session_created': False,
        }
        result = yield self.billing_api.create_transaction(**kwargs)
        self.assertEqual(result, delivered_body)

    @inlineCallbacks
    def test_create_transaction_error(self):
        response = self._mk_response(code=500, phrase="Internal Server Error",
                                     delivered_body="")

        hrm = HttpRequestMock(response)
        self.patch(billing_worker, 'http_request_full',
                   hrm.dummy_http_request_full)

        kwargs = {
            'account_number': "test-account",
            'tag_pool_name': "pool1",
            'tag_name': "1234",
            'message_direction': "Inbound",
            'session_created': False,
        }
        d = self.billing_api.create_transaction(**kwargs)
        yield self.assertFailure(d, BillingError)


class TestBillingDispatcher(VumiTestCase):

    @inlineCallbacks
    def setUp(self):
        self.vumi_helper = yield self.add_helper(VumiApiHelper())
        self.msg_helper = self.add_helper(GoMessageHelper())
        self.billing_api = BillingApiMock()
        self.ri_helper = self.vumi_helper.get_worker_helper(
            "billing_dispatcher_ri")
        self.ro_helper = self.vumi_helper.get_worker_helper(
            "billing_dispatcher_ro")

    @inlineCallbacks
    def get_dispatcher(self, **config_extras):
        config = {
            "receive_inbound_connectors": ["billing_dispatcher_ri"],
            "receive_outbound_connectors": ["billing_dispatcher_ro"],
            "api_url": "http://127.0.0.1:9090/",
            "metrics_prefix": "bar",
        }
        config.update(config_extras)
        billing_dispatcher = yield self.ri_helper.get_worker(
            BillingDispatcher, self.vumi_helper.mk_config(config))
        self.assertEqual(billing_dispatcher.billing_api.base_url,
                         config["api_url"])
        billing_dispatcher.billing_api = self.billing_api
        returnValue(billing_dispatcher)

    def add_md(self, msg, user_account=None, tag=None, is_paid=False):
        msg.payload.setdefault('helper_metadata', {})
        md = MessageMetadataHelper(self.vumi_helper.get_vumi_api(), msg)
        if user_account is not None:
            md.set_user_account(user_account)
        if tag is not None:
            md.set_tag(tag)
        if is_paid:
            md.set_paid()

    def make_dispatch_inbound(self, content, user_account=None, tag=None,
                              is_paid=False, **kw):
        msg = self.msg_helper.make_inbound(content, **kw)
        self.add_md(msg, user_account=user_account, tag=tag, is_paid=is_paid)
        return self.ri_helper.dispatch_inbound(msg).addCallback(lambda _: msg)

    def make_dispatch_outbound(self, content, user_account=None, tag=None,
                               is_paid=False, **kw):
        msg = self.msg_helper.make_outbound(content, **kw)
        self.add_md(msg, user_account=user_account, tag=tag, is_paid=is_paid)
        return self.ro_helper.dispatch_outbound(msg).addCallback(lambda _: msg)

    def assert_transaction(self, msg, direction, session_created):
        md = MessageMetadataHelper(self.vumi_helper.get_vumi_api(), msg)
        direction = {
            "inbound": BillingDispatcher.MESSAGE_DIRECTION_INBOUND,
            "outbound": BillingDispatcher.MESSAGE_DIRECTION_OUTBOUND,
        }[direction]
        self.assertEqual(self.billing_api.transactions, [{
            "account_number": md.get_account_key(),
            "tag_pool_name": md.tag[0],
            "tag_name": md.tag[1],
            "message_direction": direction,
            "session_created": session_created,
        }])

    def assert_no_transactions(self):
        self.assertEqual(self.billing_api.transactions, [])

    @inlineCallbacks
    def test_inbound_message(self):
        yield self.get_dispatcher()
        msg = yield self.make_dispatch_inbound(
            "inbound", user_account="12345", tag=("pool1", "1234"))

        self.add_md(msg, is_paid=True)
        self.assertEqual([msg], self.ro_helper.get_dispatched_inbound())
        self.assert_transaction(msg, "inbound", session_created=False)

    @inlineCallbacks
    def test_inbound_message_that_starts_session(self):
        yield self.get_dispatcher()
        msg = yield self.make_dispatch_inbound(
            "inbound", user_account="12345", tag=("pool1", "1234"),
            session_event="new")

        self.add_md(msg, is_paid=True)
        self.assertEqual([msg], self.ro_helper.get_dispatched_inbound())
        self.assert_transaction(msg, "inbound", session_created=True)

    @inlineCallbacks
    def test_inbound_message_without_user_account(self):
        yield self.get_dispatcher()
        msg = yield self.make_dispatch_inbound("hi", tag=("pool1", "1234"))
        errors = self.flushLoggedErrors(BillingError)
        self.assertEqual(len(errors), 1)
        self.assertEqual(
            [err.getErrorMessage() for err in errors],
            ["No account number found for message %s" %
                (msg.get('message_id'))])

        self.assertEqual([msg], self.ro_helper.get_dispatched_inbound())
        self.assert_no_transactions()

    @inlineCallbacks
    def test_inbound_message_without_tag(self):
        yield self.get_dispatcher()
        msg = yield self.make_dispatch_inbound("inbound", user_account="12345")
        errors = self.flushLoggedErrors(BillingError)
        self.assertEqual(len(errors), 1)
        self.assertEqual(
            [err.getErrorMessage() for err in errors],
            ["No tag found for message %s" %
                (msg.get('message_id'))])

        self.assertEqual([msg], self.ro_helper.get_dispatched_inbound())
        self.assert_no_transactions()

    @inlineCallbacks
    def test_outbound_message(self):
        yield self.get_dispatcher()
        msg = yield self.make_dispatch_outbound(
            "hi", user_account="12345", tag=("pool1", "1234"))

        self.add_md(msg, is_paid=True)
        self.assertEqual([msg], self.ri_helper.get_dispatched_outbound())
        self.assert_transaction(msg, "outbound", session_created=False)

    @inlineCallbacks
    def test_outbound_message_that_starts_session(self):
        yield self.get_dispatcher()
        msg = yield self.make_dispatch_outbound(
            "hi", user_account="12345", tag=("pool1", "1234"),
            session_event="new")

        self.add_md(msg, is_paid=True)
        self.assertEqual([msg], self.ri_helper.get_dispatched_outbound())
        self.assert_transaction(msg, "outbound", session_created=True)

    @inlineCallbacks
    def test_outbound_message_without_user_account(self):
        yield self.get_dispatcher()
        msg = yield self.make_dispatch_outbound("hi", tag=("pool1", "1234"))
        errors = self.flushLoggedErrors(BillingError)
        self.assertEqual(len(errors), 1)
        self.assertEqual(
            [err.getErrorMessage() for err in errors],
            ["No account number found for message %s" %
                (msg.get('message_id'))])

        self.assertEqual([msg], self.ri_helper.get_dispatched_outbound())
        self.assert_no_transactions()

    @inlineCallbacks
    def test_outbound_message_without_tag(self):
        yield self.get_dispatcher()
        msg = yield self.make_dispatch_outbound("hi", user_account="12345")
        errors = self.flushLoggedErrors(BillingError)
        self.assertEqual(len(errors), 1)
        self.assertEqual(
            [err.getErrorMessage() for err in errors],
            ["No tag found for message %s" %
                (msg.get('message_id'))])

        self.assertEqual([msg], self.ri_helper.get_dispatched_outbound())
        self.assert_no_transactions()

    @inlineCallbacks
    def test_event_message(self):
        yield self.get_dispatcher()
        ack = self.msg_helper.make_ack()
        yield self.ri_helper.dispatch_event(ack)
        self.assertEqual([ack], self.ro_helper.get_dispatched_events())
        self.assert_no_transactions()
