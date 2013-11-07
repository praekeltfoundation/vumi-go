import json
import decimal

from twisted.internet.defer import inlineCallbacks, returnValue
from twisted.trial.unittest import TestCase
from twisted.web.client import Agent, Request, Response

from vumi.utils import mkheaders, StringProducer

from go.vumitools.tests.utils import AppWorkerTestCase
from go.vumitools import billing_worker
from go.vumitools.billing_worker import BillingApi, BillingDispatcher
from go.vumitools.utils import MessageMetadataHelper

from go.billing.api import BillingError
from go.billing.utils import JSONEncoder


class BillingApiMock(object):

    def __init__(self, base_url):
        self.base_url = base_url

    def create_transaction(self, account_number, tag_pool_name,
                           tag_name, message_direction):
        return {
            "id": 1,
            "account_number": account_number,
            "tag_pool_name": tag_pool_name,
            "tag_name": tag_name,
            "message_direction": message_direction,
            "message_cost": 80,
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


class TestBillingApi(TestCase):

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
            'message_direction': "Inbound"
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
            'message_direction': "Inbound"
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
            'message_direction': "Inbound"
        }
        d = self.billing_api.create_transaction(**kwargs)
        yield self.assertFailure(d, BillingError)


class TestBillingDispatcher(AppWorkerTestCase):

    @inlineCallbacks
    def setUp(self):
        yield super(TestBillingDispatcher, self).setUp()
        self.dispatcher = yield self.get_dispatcher()
        self.vumi_api = self.dispatcher.vumi_api

    @inlineCallbacks
    def get_dispatcher(self, **config_extras):
        config = {
            "receive_inbound_connectors": [
                "billing_dispatcher_ri"
            ],
            "receive_outbound_connectors": [
                "billing_dispatcher_ro"
            ],
            "api_url": "http://127.0.0.1:9090/",
            "metrics_prefix": "bar"
        }
        config.update(config_extras)
        billing_dispatcher = yield self.get_worker(
            self.mk_config(config), BillingDispatcher)
        billing_dispatcher.billing_api = BillingApiMock(config["api_url"])
        returnValue(billing_dispatcher)

    def with_md(self, msg, user_account=None, tag=None, is_paid=False):
        msg.payload.setdefault('helper_metadata', {})
        md = MessageMetadataHelper(self.vumi_api, msg)
        if user_account is not None:
            md.set_user_account(user_account)
        if tag is not None:
            md.set_tag(tag)
        if is_paid:
            md.set_paid()
        return msg

    @inlineCallbacks
    def test_inbound_message(self):
        yield self.get_dispatcher()
        msg = self.with_md(self.mkmsg_in(), user_account="12345",
                           tag=("pool1", "1234"))

        yield self.dispatch_inbound(msg, 'billing_dispatcher_ri')
        self.with_md(msg, is_paid=True)
        self.assertEqual(
            [msg], self.get_dispatched_inbound('billing_dispatcher_ro'))

    @inlineCallbacks
    def test_outbound_message(self):
        yield self.get_dispatcher()
        msg = self.with_md(self.mkmsg_out(), user_account="12345",
                           tag=("pool1", "1234"))

        yield self.dispatch_outbound(msg, 'billing_dispatcher_ro')
        self.with_md(msg, is_paid=True)
        self.assertEqual(
            [msg], self.get_dispatched_outbound('billing_dispatcher_ri'))

    @inlineCallbacks
    def test_event_message(self):
        yield self.get_dispatcher()
        ack = self.mkmsg_ack()
        yield self.dispatch_event(ack, 'billing_dispatcher_ri')
        self.assertEqual(
            [ack], self.get_dispatched_events('billing_dispatcher_ro'))
