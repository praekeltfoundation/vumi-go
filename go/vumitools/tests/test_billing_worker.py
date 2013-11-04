import decimal

from twisted.internet.defer import inlineCallbacks, returnValue

from go.vumitools.tests.utils import AppWorkerTestCase
from go.vumitools.billing_worker import BillingDispatcher
from go.vumitools.utils import MessageMetadataHelper


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

    def with_md(self, msg, user_account=None, conv=None, router=None,
                tag=None, is_paid=False):
        msg.payload.setdefault('helper_metadata', {})
        md = MessageMetadataHelper(self.vumi_api, msg)
        if user_account is not None:
            md.set_user_account(user_account)
        if conv is not None:
            conv_type, conv_key = conv
            md.set_conversation_info(conv_type, conv_key)
            md.set_user_account(self.user_account_key)
        if router is not None:
            router_type, router_key = router
            md.set_router_info(router_type, router_key)
            md.set_user_account(self.user_account_key)
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
