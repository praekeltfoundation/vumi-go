import decimal

from twisted.internet.defer import inlineCallbacks, returnValue

from go.vumitools.routing import RoutingMetadata
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
                endpoint=None, tag=None, hops=None, outbound_hops_from=None,
                is_paid=False):
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
        if endpoint is None:
            endpoint = msg.get_routing_endpoint()
        msg.set_routing_endpoint(endpoint)
        if tag is not None:
            md.set_tag(tag)
        if is_paid:
            md.set_paid()
        if hops is not None:
            rmeta = RoutingMetadata(msg)
            for src, dst in zip(hops[:-1], hops[1:]):
                rmeta.push_hop(src, dst)
        if outbound_hops_from is not None:
            rmeta = RoutingMetadata(msg)
            outbound_rmeta = RoutingMetadata(outbound_hops_from)
            rmeta.set_outbound_hops(outbound_rmeta.get_hops())
        return msg

    def assert_rkeys_used(self, *rkeys):
        self.assertEqual(set(rkeys), set(self._amqp.dispatched['vumi'].keys()))

    @inlineCallbacks
    def mk_msg_reply(self, **kw):
        "Create and store an outbound message, then create a reply for it."
        msg = self.with_md(self.mkmsg_in(), **kw)
        yield self.vumi_api.mdb.add_inbound_message(msg)
        reply = msg.reply(content="Reply")
        returnValue((msg, reply))

    @inlineCallbacks
    def mk_msg_ack(self, **kw):
        "Create and store an outbound message, then create an ack for it."
        msg = self.with_md(self.mkmsg_out(), **kw)
        yield self.vumi_api.mdb.add_outbound_message(msg)
        ack = self.mkmsg_ack(user_message_id=msg['message_id'])
        returnValue((msg, ack))

    @inlineCallbacks
    def test_inbound_message(self):
        yield self.get_dispatcher()
        msg = self.with_md(self.mkmsg_in(), user_account="12345",
                           tag=("pool1", "1234"))

        yield self.dispatch_inbound(msg, 'billing_dispatcher_ri')
        self.assert_rkeys_used('billing_dispatcher_ri.inbound',
                               'billing_dispatcher_ro.inbound')

        self.with_md(msg, is_paid=True)
        self.assertEqual(
            [msg], self.get_dispatched_inbound('billing_dispatcher_ro'))

    @inlineCallbacks
    def test_outbound_message(self):
        yield self.get_dispatcher()
        msg = self.with_md(self.mkmsg_out(), user_account="12345",
                           tag=("pool1", "1234"))

        yield self.dispatch_outbound(msg, 'billing_dispatcher_ro')
        self.assert_rkeys_used('billing_dispatcher_ro.outbound',
                               'billing_dispatcher_ri.outbound')

        self.with_md(msg, is_paid=True)
        self.assertEqual(
            [msg], self.get_dispatched_outbound('billing_dispatcher_ri'))
