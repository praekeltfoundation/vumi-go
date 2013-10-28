from twisted.internet.defer import inlineCallbacks, returnValue

from go.vumitools.routing import (
    AccountRoutingTableDispatcher, RoutingMetadata, RoutingError)
from go.vumitools.billing_worker import BillingDispatcher
from go.vumitools.tests.utils import GoTestCase, AppWorkerTestCase
from go.vumitools.utils import MessageMetadataHelper
from go.vumitools.routing_table import RoutingTable


class TestRoutingMetadata(GoTestCase):
    def mk_msg_rmeta(self, **routing_metadata):
        # We don't need a real message, just a container for routing_metadata.
        msg = {'routing_metadata': routing_metadata}
        return msg, RoutingMetadata(msg)

    def set_hops(self, msg, hops):
        msg['routing_metadata']['go_hops'] = hops

    def set_outbound_hops(self, msg, hops):
        msg['routing_metadata']['go_outbound_hops'] = hops

    def assert_hops(self, msg, hops):
        self.assertEqual(hops, msg['routing_metadata'].get('go_hops'))

    def assert_outbound_hops(self, msg, hops):
        self.assertEqual(hops, msg['routing_metadata'].get('go_outbound_hops'))

    def test_get_hops(self):
        msg, rmeta = self.mk_msg_rmeta()
        self.assert_hops(msg, None)
        self.assertEqual([], rmeta.get_hops())
        self.assert_hops(msg, [])
        self.assertEqual([], rmeta.get_hops())
        self.set_hops(msg, [
            [['sc1', 'se1'], ['dc1', 'de1']],
        ])
        self.assert_hops(msg, [[['sc1', 'se1'], ['dc1', 'de1']]])
        self.assertEqual([
            [['sc1', 'se1'], ['dc1', 'de1']],
        ], rmeta.get_hops())

    def test_get_outbound_hops(self):
        msg, rmeta = self.mk_msg_rmeta()
        self.assert_outbound_hops(msg, None)
        self.assertEqual(None, rmeta.get_outbound_hops())
        self.set_outbound_hops(msg, [
            [['sc1', 'se1'], ['dc1', 'de1']],
        ])
        self.assert_outbound_hops(msg, [
            [['sc1', 'se1'], ['dc1', 'de1']],
        ])
        self.assertEqual([
            [['sc1', 'se1'], ['dc1', 'de1']],
        ], rmeta.get_outbound_hops())

    def test_set_outbound_hops(self):
        msg, rmeta = self.mk_msg_rmeta()
        self.assert_outbound_hops(msg, None)
        rmeta.set_outbound_hops([
            [['sc1', 'se1'], ['dc1', 'de1']],
        ])
        self.assert_outbound_hops(msg, [
            [['sc1', 'se1'], ['dc1', 'de1']],
        ])

    def test_push_hop(self):
        msg, rmeta = self.mk_msg_rmeta()
        self.assert_hops(msg, None)
        rmeta.push_hop(['sc1', 'se1'], ['dc1', 'de1'])
        self.assert_hops(msg, [
            [['sc1', 'se1'], ['dc1', 'de1']],
        ])
        rmeta.push_hop(['sc2', 'se2'], ['dc2', 'de2'])
        self.assert_hops(msg, [
            [['sc1', 'se1'], ['dc1', 'de1']],
            [['sc2', 'se2'], ['dc2', 'de2']],
        ])
        rmeta.push_hop(['sc2', 'se2'], ['dc2', 'de2'])
        self.assert_hops(msg, [
            [['sc1', 'se1'], ['dc1', 'de1']],
            [['sc2', 'se2'], ['dc2', 'de2']],
            [['sc2', 'se2'], ['dc2', 'de2']],
        ])

    def test_push_source_no_hops(self):
        msg, rmeta = self.mk_msg_rmeta()
        self.assert_hops(msg, None)
        rmeta.push_source('sconn', 'sep')
        self.assert_hops(msg, [
            [['sconn', 'sep'], None],
        ])

    def test_push_source_with_hops(self):
        msg, rmeta = self.mk_msg_rmeta(go_hops=[
            [['sc1', 'se1'], ['dc1', 'de1']],
        ])
        self.assert_hops(msg, [
            [['sc1', 'se1'], ['dc1', 'de1']],
        ])
        rmeta.push_source('sconn', 'sep')
        self.assert_hops(msg, [
            [['sc1', 'se1'], ['dc1', 'de1']],
            [['sconn', 'sep'], None],
        ])

    def test_push_source_twice(self):
        msg, rmeta = self.mk_msg_rmeta()
        rmeta.push_source('sc1', 'se1')
        self.assert_hops(msg, [
            [['sc1', 'se1'], None],
        ])
        self.assertRaises(RoutingError, rmeta.push_source, 'sc1', 'se1')
        self.assert_hops(msg, [
            [['sc1', 'se1'], None],
        ])
        self.assertRaises(RoutingError, rmeta.push_source, 'sc2', 'se2')

    def test_push_destination_no_hops(self):
        msg, rmeta = self.mk_msg_rmeta(go_hops=[[['sconn', 'sep'], None]])
        self.assert_hops(msg, [[['sconn', 'sep'], None]])
        rmeta.push_destination('dconn', 'dep')
        self.assert_hops(msg, [
            [['sconn', 'sep'], ['dconn', 'dep']],
        ])

    def test_push_destination_with_hops(self):
        msg, rmeta = self.mk_msg_rmeta(go_hops=[
            [['sc1', 'se1'], ['dc1', 'de1']],
            [['sconn', 'sep'], None],
        ])
        self.assert_hops(msg, [
            [['sc1', 'se1'], ['dc1', 'de1']],
            [['sconn', 'sep'], None],
        ])
        rmeta.push_destination('dconn', 'dep')
        self.assert_hops(msg, [
            [['sc1', 'se1'], ['dc1', 'de1']],
            [['sconn', 'sep'], ['dconn', 'dep']],
        ])

    def test_push_destination_twice(self):
        msg, rmeta = self.mk_msg_rmeta(go_hops=[[['sc1', 'se1'], None]])
        rmeta.push_destination('dc1', 'de1')
        self.assert_hops(msg, [
            [['sc1', 'se1'], ['dc1', 'de1']],
        ])
        self.assertRaises(RoutingError, rmeta.push_destination, 'dc1', 'de1')
        self.assert_hops(msg, [
            [['sc1', 'se1'], ['dc1', 'de1']],
        ])
        self.assertRaises(RoutingError, rmeta.push_destination, 'dc2', 'de2')

    def assert_next_hop(self, hops, outbound, expected):
        msg, rmeta = self.mk_msg_rmeta(go_hops=hops, go_outbound_hops=outbound)
        self.assertEqual(expected, rmeta.next_hop())

    def test_next_hop_without_hops(self):
        self.assert_next_hop(None, None, None)
        self.assert_next_hop([], [], None)
        self.assert_next_hop([1, 2, 3], [], None)
        self.assert_next_hop([1, 2, 3], [1, 2], None)

    def test_next_hop_dest_set(self):
        self.assert_next_hop([
            [['sc1', 'se1'], ['dc1', 'de1']],
        ], [
            [['dc1', 'de1'], ['sc1', 'se1']],
        ], None)

    def test_next_hop_first(self):
        self.assert_next_hop([
            [['sc1', 'se1'], None],
        ], [
            [['dc1', 'de1'], ['sc1', 'se1']],
        ], ['dc1', 'de1'])

    def test_next_hop_second(self):
        self.assert_next_hop([
            [['sc1', 'se1'], ['sc1', 'de1']],
            [['sc2', 'se2'], None],
        ], [
            [['dc3', 'de3'], ['sc3', 'se3']],
            [['dc2', 'de2'], ['sc2', 'se2']],
            [['dc1', 'de1'], ['sc1', 'se1']],
        ], ['dc2', 'de2'])

    def assert_next_router_endpoint(self, hops, outbound, expected):
        msg, rmeta = self.mk_msg_rmeta(go_hops=hops, go_outbound_hops=outbound)
        self.assertEqual(expected, rmeta.next_router_endpoint())

    def test_next_router_endpoint_without_hops(self):
        self.assert_next_router_endpoint(None, None, None)
        self.assert_next_router_endpoint([], [], None)
        self.assert_next_router_endpoint([1, 2, 3], [], None)
        self.assert_next_router_endpoint([1, 2, 3], [1, 2], None)

    def test_next_router_endpoint_first(self):
        self.assert_next_router_endpoint([], [
            [['dc1', 'de1'], ['sc1', 'se1']],
        ], 'se1')

    def test_next_router_endpoint_second(self):
        self.assert_next_router_endpoint([
            [['sc1', 'se1'], ['sc1', 'de1']],
        ], [
            [['dc3', 'de3'], ['sc3', 'se3']],
            [['dc2', 'de2'], ['sc2', 'se2']],
            [['dc1', 'de1'], ['sc1', 'se1']],
        ], 'se2')


class RoutingTableDispatcherTestCase(AppWorkerTestCase):
    """Base class for ``AccountRoutingTableDispatcher`` test cases"""

    @inlineCallbacks
    def setup_routing_table_dispatcher_test(self):
        self.dispatcher = yield self.get_dispatcher()
        self.vumi_api = self.dispatcher.vumi_api

        user_account = yield self.mk_user(self.vumi_api, u'testuser')
        user_account.routing_table = RoutingTable({
            # Transport side
            "TRANSPORT_TAG:pool1:1234": {
                "default": ["CONVERSATION:app1:conv1", "default"]},
            "TRANSPORT_TAG:pool1:5678": {
                "default": ["CONVERSATION:app1:conv1", "other"]},
            "TRANSPORT_TAG:pool1:9012": {
                "default": ["CONVERSATION:app2:conv2", "default"]},
            # Application side
            "CONVERSATION:app1:conv1": {
                "default": ["TRANSPORT_TAG:pool1:1234", "default"],
                "other": ["TRANSPORT_TAG:pool1:5678", "default"],
            },
            "CONVERSATION:app2:conv2": {
                "default": ["TRANSPORT_TAG:pool1:9012", "default"],
            },
            # Router outbound
            "ROUTER:router:router1:INBOUND": {
                "default": ["TRANSPORT_TAG:pool1:1234", "default"],
                "other": ["TRANSPORT_TAG:pool1:5678", "default"],
            },
            # Router inbound
            "ROUTER:router:router1:OUTBOUND": {
                "default": ["CONVERSATION:app1:conv1", "default"],
                "other": ["CONVERSATION:app2:conv2", "yet-another"],
            },
        })
        yield user_account.save()

        self.user_account_key = user_account.key
        self.user_api = self.vumi_api.get_user_api(self.user_account_key)
        tag1, tag2, tag3 = yield self.setup_tagpool(
            u"pool1", [u"1234", u"5678", u"9012"])
        yield self.user_api.acquire_specific_tag(tag1)
        yield self.user_api.acquire_specific_tag(tag2)
        yield self.user_api.acquire_specific_tag(tag3)

    @inlineCallbacks
    def get_dispatcher(self, **config_extras):
        config = {
            "receive_inbound_connectors": [
                "sphex", "router_ro"
            ],
            "receive_outbound_connectors": [
                "app1", "app2", "router_ri", "optout"
            ],
            "metrics_prefix": "foo",
            "application_connector_mapping": {
                "app1": "app1",
                "app2": "app2",
            },
            "router_inbound_connector_mapping": {
                "router": "router_ro",
            },
            "router_outbound_connector_mapping": {
                "router": "router_ri",
            },
            "opt_out_connector": "optout"
        }
        config.update(config_extras)
        dispatcher = yield self.get_worker(
            self.mk_config(config), AccountRoutingTableDispatcher)
        returnValue(dispatcher)

    @inlineCallbacks
    def get_billing_dispatcher(self, **config_extras):
        config = {
            "receive_inbound_connectors": [
                "billing_dispatcher_ri"
            ],
            "receive_outbound_connectors": [
                "billing_dispatcher_ro"
            ],
            "metrics_prefix": "bar"
        }
        config.update(config_extras)
        billing_dispatcher = yield self.get_worker(
            self.mk_config(config), BillingDispatcher)
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


class TestRoutingTableDispatcher(RoutingTableDispatcherTestCase):

    @inlineCallbacks
    def setUp(self):
        yield super(TestRoutingTableDispatcher, self).setUp()
        yield self.setup_routing_table_dispatcher_test()

    @inlineCallbacks
    def test_inbound_message_from_transport_to_app1(self):
        yield self.get_dispatcher()
        msg = self.with_md(self.mkmsg_in(), tag=("pool1", "1234"))
        yield self.dispatch_inbound(msg, 'sphex')
        self.assert_rkeys_used('sphex.inbound', 'app1.inbound')
        self.with_md(msg, conv=('app1', 'conv1'),
                     hops=[
                         ['TRANSPORT_TAG:pool1:1234', 'default'],
                         ['CONVERSATION:app1:conv1', 'default'],
                     ])
        self.assertEqual([msg], self.get_dispatched_inbound('app1'))

    @inlineCallbacks
    def test_inbound_message_from_transport_to_app2(self):
        yield self.get_dispatcher()
        msg = self.with_md(self.mkmsg_in(), tag=("pool1", "9012"))
        yield self.dispatch_inbound(msg, 'sphex')
        self.assert_rkeys_used('sphex.inbound', 'app2.inbound')
        self.with_md(msg, conv=('app2', 'conv2'),
                     hops=[
                         ['TRANSPORT_TAG:pool1:9012', 'default'],
                         ['CONVERSATION:app2:conv2', 'default'],
                     ])
        self.assertEqual([msg], self.get_dispatched_inbound('app2'))

    @inlineCallbacks
    def test_inbound_message_from_transport_to_custom_endpoint(self):
        yield self.get_dispatcher()
        msg = self.with_md(self.mkmsg_in(), tag=("pool1", "5678"))
        yield self.dispatch_inbound(msg, 'sphex')
        self.assert_rkeys_used('sphex.inbound', 'app1.inbound')
        self.with_md(msg, conv=('app1', 'conv1'), endpoint='other',
                     hops=[
                         ['TRANSPORT_TAG:pool1:5678', 'default'],
                         ['CONVERSATION:app1:conv1', 'other'],
                     ])
        self.assertEqual([msg], self.get_dispatched_inbound('app1'))

    @inlineCallbacks
    def test_inbound_message_from_transport_to_optout(self):
        yield self.get_dispatcher()
        tag = ("pool1", "1234")
        msg = self.with_md(self.mkmsg_in(), tag=tag)
        msg['helper_metadata']['optout'] = {'optout': True}
        yield self.dispatch_inbound(msg, 'sphex')
        self.assert_rkeys_used('sphex.inbound', 'optout.inbound')
        self.with_md(msg, user_account=self.user_account_key,
                     hops=[
                         ['TRANSPORT_TAG:pool1:1234', 'default'],
                         ['OPT_OUT', 'default'],
                     ])
        self.assertEqual([msg], self.get_dispatched_inbound('optout'))

    @inlineCallbacks
    def test_inbound_message_from_router(self):
        yield self.get_dispatcher()
        msg = self.with_md(self.mkmsg_out(), router=('router', 'router1'))
        yield self.dispatch_inbound(msg, 'router_ro')
        self.assert_rkeys_used('router_ro.inbound', 'app1.inbound')
        self.with_md(msg, conv=("app1", "conv1"),
                     hops=[
                         ['ROUTER:router:router1:OUTBOUND', 'default'],
                         ['CONVERSATION:app1:conv1', 'default'],
                     ])
        self.assertEqual([msg], self.get_dispatched_inbound('app1'))

    @inlineCallbacks
    def test_inbound_message_from_router_to_custom_endpoint(self):
        yield self.get_dispatcher()
        msg = self.with_md(self.mkmsg_out(), router=('router', 'router1'),
                           endpoint='other')
        yield self.dispatch_inbound(msg, 'router_ro')
        self.assert_rkeys_used('router_ro.inbound', 'app2.inbound')
        self.with_md(msg, conv=("app2", "conv2"), endpoint='yet-another',
                     hops=[
                         ['ROUTER:router:router1:OUTBOUND', 'other'],
                         ['CONVERSATION:app2:conv2', 'yet-another'],
                     ])
        self.assertEqual([msg], self.get_dispatched_inbound('app2'))

    @inlineCallbacks
    def test_outbound_message_from_optout_to_transport(self):
        yield self.get_dispatcher()
        tag = ("pool1", "1234")
        msg, reply = yield self.mk_msg_reply(tag=tag)
        yield self.dispatch_outbound(reply, 'optout')
        self.assert_rkeys_used('optout.outbound', 'sphex.outbound')
        self.with_md(reply, tag=tag, user_account=self.user_account_key,
                     hops=[
                         ['OPT_OUT', 'default'],
                         ['TRANSPORT_TAG:pool1:1234', 'default'],
                     ])
        self.assertEqual([reply], self.get_dispatched_outbound('sphex'))

    @inlineCallbacks
    def test_outbound_message_from_conversation_in_app1(self):
        yield self.get_dispatcher()
        msg = self.with_md(self.mkmsg_out(), conv=('app1', 'conv1'))
        yield self.dispatch_outbound(msg, 'app1')
        self.assert_rkeys_used('app1.outbound', 'sphex.outbound')
        self.with_md(msg, tag=("pool1", "1234"),
                     hops=[
                         ['CONVERSATION:app1:conv1', 'default'],
                         ['TRANSPORT_TAG:pool1:1234', 'default'],
                     ])
        self.assertEqual([msg], self.get_dispatched_outbound('sphex'))

    @inlineCallbacks
    def test_outbound_message_from_conversation_in_app2(self):
        yield self.get_dispatcher()
        msg = self.with_md(self.mkmsg_out(), conv=('app2', 'conv2'))
        yield self.dispatch_outbound(msg, 'app2')
        self.assert_rkeys_used('app2.outbound', 'sphex.outbound')
        self.with_md(msg, tag=("pool1", "9012"),
                     hops=[
                         ['CONVERSATION:app2:conv2', 'default'],
                         ['TRANSPORT_TAG:pool1:9012', 'default'],
                     ])
        self.assertEqual([msg], self.get_dispatched_outbound('sphex'))

    @inlineCallbacks
    def test_outbound_message_from_conversation_via_custom_endpoint(self):
        yield self.get_dispatcher()
        msg = self.with_md(self.mkmsg_out(), conv=('app1', 'conv1'),
                           endpoint='other')
        yield self.dispatch_outbound(msg, 'app1')
        self.assert_rkeys_used('app1.outbound', 'sphex.outbound')
        self.with_md(msg, tag=("pool1", "5678"), endpoint='default',
                     hops=[
                         ['CONVERSATION:app1:conv1', 'other'],
                         ['TRANSPORT_TAG:pool1:5678', 'default'],
                     ])
        self.assertEqual([msg], self.get_dispatched_outbound('sphex'))

    @inlineCallbacks
    def test_outbound_message_from_router(self):
        yield self.get_dispatcher()
        msg = self.with_md(self.mkmsg_out(), router=('router', 'router1'))
        yield self.dispatch_outbound(msg, 'router_ri')
        self.assert_rkeys_used('router_ri.outbound', 'sphex.outbound')
        self.with_md(msg, tag=("pool1", "1234"),
                     hops=[
                         ['ROUTER:router:router1:INBOUND', 'default'],
                         ['TRANSPORT_TAG:pool1:1234', 'default'],
                     ])
        self.assertEqual([msg], self.get_dispatched_outbound('sphex'))

    @inlineCallbacks
    def test_outbound_message_from_router_via_custom_endpoint(self):
        yield self.get_dispatcher()
        msg = self.with_md(self.mkmsg_out(), router=('router', 'router1'),
                           endpoint='other')
        yield self.dispatch_outbound(msg, 'router_ri')
        self.assert_rkeys_used('router_ri.outbound', 'sphex.outbound')
        self.with_md(msg, tag=("pool1", "5678"), endpoint='default',
                     hops=[
                         ['ROUTER:router:router1:INBOUND', 'other'],
                         ['TRANSPORT_TAG:pool1:5678', 'default'],
                     ])
        self.assertEqual([msg], self.get_dispatched_outbound('sphex'))

    @inlineCallbacks
    def test_event_routing_to_app1(self):
        yield self.get_dispatcher()
        msg, ack = yield self.mk_msg_ack(
            tag=('pool1', '1234'), user_account=self.user_account_key,
            hops=[
                ['CONVERSATION:app1:conv1', 'default'],
                ['TRANSPORT_TAG:pool1:1234', 'default'],
            ])
        yield self.dispatch_event(ack, 'sphex')
        self.assert_rkeys_used('sphex.event', 'app1.event')
        self.with_md(ack, tag=('pool1', '1234'), conv=('app1', 'conv1'),
                     hops=[
                         ['TRANSPORT_TAG:pool1:1234', 'default'],
                         ['CONVERSATION:app1:conv1', 'default'],
                     ], outbound_hops_from=msg)
        self.assertEqual([ack], self.get_dispatched_events('app1'))

    @inlineCallbacks
    def test_event_routing_to_app2(self):
        yield self.get_dispatcher()
        msg, ack = yield self.mk_msg_ack(
            tag=('pool1', '9012'), user_account=self.user_account_key,
            hops=[
                ['CONVERSATION:app2:conv2', 'default'],
                ['TRANSPORT_TAG:pool1:9012', 'default'],
            ])
        yield self.dispatch_event(ack, 'sphex')
        self.assert_rkeys_used('sphex.event', 'app2.event')
        self.with_md(ack, tag=('pool1', '9012'), conv=('app2', 'conv2'),
                     hops=[
                         ['TRANSPORT_TAG:pool1:9012', 'default'],
                         ['CONVERSATION:app2:conv2', 'default'],
                     ], outbound_hops_from=msg)
        self.assertEqual([ack], self.get_dispatched_events('app2'))

    @inlineCallbacks
    def test_event_routing_via_custom_endpoint(self):
        yield self.get_dispatcher()
        msg, ack = yield self.mk_msg_ack(endpoint='other',
            tag=('pool1', '5678'), user_account=self.user_account_key,
            hops=[
                ['CONVERSATION:app1:conv1', 'other'],
                ['TRANSPORT_TAG:pool1:5678', 'default'],
            ])
        yield self.dispatch_event(ack, 'sphex')
        self.assert_rkeys_used('sphex.event', 'app1.event')
        self.with_md(ack, tag=('pool1', '5678'), conv=('app1', 'conv1'),
                     endpoint='other',
                     hops=[
                         ['TRANSPORT_TAG:pool1:5678', 'default'],
                         ['CONVERSATION:app1:conv1', 'other']
                     ], outbound_hops_from=msg)
        self.assertEqual([ack], self.get_dispatched_events('app1'))

    @inlineCallbacks
    def test_outbound_message_gets_transport_fields(self):
        yield self.get_dispatcher()
        yield self.vumi_api.tpm.set_metadata("pool1", {
            'transport_name': 'sphex',
            'transport_type': 'sms',
        })
        msg = self.with_md(self.mkmsg_out(), conv=('app1', 'conv1'))
        msg['transport_name'] = None
        msg['transport_type'] = None
        yield self.dispatch_outbound(msg, 'app1')
        self.assert_rkeys_used('app1.outbound', 'sphex.outbound')
        msg['transport_name'] = 'sphex'
        msg['transport_type'] = 'sms'
        self.with_md(msg, tag=("pool1", "1234"), hops=[
            ['CONVERSATION:app1:conv1', 'default'],
            ['TRANSPORT_TAG:pool1:1234', 'default'],
        ])
        self.assertEqual([msg], self.get_dispatched_outbound('sphex'))


class TestRoutingTableDispatcherWithBilling(RoutingTableDispatcherTestCase):

    @inlineCallbacks
    def setUp(self):
        yield super(TestRoutingTableDispatcherWithBilling, self).setUp()
        yield self.setup_routing_table_dispatcher_test()

    @inlineCallbacks
    def get_dispatcher(self, **config_extras):
        config = {
            "receive_inbound_connectors": [
                "sphex", "router_ro", "billing_dispatcher_ro"
            ],
            "receive_outbound_connectors": [
                "app1", "app2", "router_ri", "optout",
                "billing_dispatcher_ri"
            ],
            "billing_inbound_connector": "billing_dispatcher_ri",
            "billing_outbound_connector": "billing_dispatcher_ro"
        }
        config.update(config_extras)
        dispatcher = yield super(TestRoutingTableDispatcherWithBilling, self)\
            .get_dispatcher(**config)
        returnValue(dispatcher)

    @inlineCallbacks
    def test_inbound_message_from_transport_to_app1(self):
        yield self.get_dispatcher()
        yield self.get_billing_dispatcher()
        msg = self.with_md(self.mkmsg_in(), tag=("pool1", "1234"))
        yield self.dispatch_inbound(msg, 'sphex')
        self.assert_rkeys_used('sphex.inbound', 'app1.inbound',
                               'billing_dispatcher_ri.inbound',
                               'billing_dispatcher_ro.inbound')

        hops = [
            ['TRANSPORT_TAG:pool1:1234', 'default'],
            ['BILLING:INBOUND', 'default'],
            ['CONVERSATION:app1:conv1', 'default']
        ]
        self.with_md(msg, conv=('app1', 'conv1'), hops=hops, is_paid=True)
        self.assertEqual([msg], self.get_dispatched_inbound('app1'))

    @inlineCallbacks
    def test_inbound_message_from_transport_to_app2(self):
        yield self.get_dispatcher()
        yield self.get_billing_dispatcher()
        msg = self.with_md(self.mkmsg_in(), tag=("pool1", "9012"))
        yield self.dispatch_inbound(msg, 'sphex')
        self.assert_rkeys_used('sphex.inbound', 'app2.inbound',
                               'billing_dispatcher_ri.inbound',
                               'billing_dispatcher_ro.inbound')

        hops = [
            ['TRANSPORT_TAG:pool1:9012', 'default'],
            ['BILLING:INBOUND', 'default'],
            ['CONVERSATION:app2:conv2', 'default'],
        ]
        self.with_md(msg, conv=('app2', 'conv2'), hops=hops, is_paid=True)
        self.assertEqual([msg], self.get_dispatched_inbound('app2'))

    @inlineCallbacks
    def test_inbound_message_from_transport_to_custom_endpoint(self):
        yield self.get_dispatcher()
        yield self.get_billing_dispatcher()
        msg = self.with_md(self.mkmsg_in(), tag=("pool1", "5678"))
        yield self.dispatch_inbound(msg, 'sphex')
        self.assert_rkeys_used('sphex.inbound', 'app1.inbound',
                               'billing_dispatcher_ri.inbound',
                               'billing_dispatcher_ro.inbound')

        hops = [
            ['TRANSPORT_TAG:pool1:5678', 'default'],
            ['BILLING:INBOUND', 'default'],
            ['CONVERSATION:app1:conv1', 'other'],
        ]
        self.with_md(msg, conv=('app1', 'conv1'), endpoint='other',
                     hops=hops, is_paid=True)

        self.assertEqual([msg], self.get_dispatched_inbound('app1'))

    @inlineCallbacks
    def test_inbound_message_from_transport_to_optout(self):
        yield self.get_dispatcher()
        yield self.get_billing_dispatcher()
        tag = ("pool1", "1234")
        msg = self.with_md(self.mkmsg_in(), tag=tag)
        msg['helper_metadata']['optout'] = {'optout': True}
        yield self.dispatch_inbound(msg, 'sphex')
        self.assert_rkeys_used('sphex.inbound', 'optout.inbound')
        hops = [
            ['TRANSPORT_TAG:pool1:1234', 'default'],
            ['OPT_OUT', 'default'],
        ]
        self.with_md(msg, user_account=self.user_account_key, hops=hops)
        self.assertEqual([msg], self.get_dispatched_inbound('optout'))

    @inlineCallbacks
    def test_inbound_message_from_router(self):
        yield self.get_dispatcher()
        yield self.get_billing_dispatcher()
        msg = self.with_md(self.mkmsg_out(), router=('router', 'router1'),
                           is_paid=True)

        yield self.dispatch_inbound(msg, 'router_ro')
        self.assert_rkeys_used('router_ro.inbound', 'app1.inbound')
        hops = [
            ['ROUTER:router:router1:OUTBOUND', 'default'],
            ['CONVERSATION:app1:conv1', 'default'],
        ]
        self.with_md(msg, conv=("app1", "conv1"), hops=hops)
        self.assertEqual([msg], self.get_dispatched_inbound('app1'))

    @inlineCallbacks
    def test_inbound_message_from_router_to_custom_endpoint(self):
        yield self.get_dispatcher()
        yield self.get_billing_dispatcher()
        msg = self.with_md(self.mkmsg_out(), router=('router', 'router1'),
                           endpoint='other', is_paid=True)

        yield self.dispatch_inbound(msg, 'router_ro')
        self.assert_rkeys_used('router_ro.inbound', 'app2.inbound')
        hops = [
            ['ROUTER:router:router1:OUTBOUND', 'other'],
            ['CONVERSATION:app2:conv2', 'yet-another'],
        ]
        self.with_md(msg, conv=("app2", "conv2"), endpoint='yet-another',
                     hops=hops)

        self.assertEqual([msg], self.get_dispatched_inbound('app2'))

    @inlineCallbacks
    def test_outbound_message_from_optout_to_transport(self):
        yield self.get_dispatcher()
        yield self.get_billing_dispatcher()
        tag = ("pool1", "1234")
        msg, reply = yield self.mk_msg_reply(tag=tag)
        yield self.dispatch_outbound(reply, 'optout')
        self.assert_rkeys_used('optout.outbound', 'sphex.outbound')
        hops = [
            ['OPT_OUT', 'default'],
            ['TRANSPORT_TAG:pool1:1234', 'default'],
        ]
        self.with_md(reply, tag=tag, user_account=self.user_account_key,
                     hops=hops)

        self.assertEqual([reply], self.get_dispatched_outbound('sphex'))

    @inlineCallbacks
    def test_outbound_message_from_conversation_in_app1(self):
        yield self.get_dispatcher()
        yield self.get_billing_dispatcher()
        msg = self.with_md(self.mkmsg_out(), conv=('app1', 'conv1'))
        yield self.dispatch_outbound(msg, 'app1')
        self.assert_rkeys_used(
            'app1.outbound', 'billing_dispatcher_ro.outbound',
            'billing_dispatcher_ri.outbound', 'sphex.outbound')

        hops = [
            ['CONVERSATION:app1:conv1', 'default'],
            ['BILLING:OUTBOUND', 'default'],
            ['TRANSPORT_TAG:pool1:1234', 'default']
        ]
        self.with_md(msg, tag=("pool1", "1234"), hops=hops, is_paid=True)
        self.assertEqual([msg], self.get_dispatched_outbound('sphex'))

    @inlineCallbacks
    def test_outbound_message_from_conversation_in_app2(self):
        yield self.get_dispatcher()
        yield self.get_billing_dispatcher()
        msg = self.with_md(self.mkmsg_out(), conv=('app2', 'conv2'))
        yield self.dispatch_outbound(msg, 'app2')
        self.assert_rkeys_used(
            'app2.outbound', 'billing_dispatcher_ro.outbound',
            'billing_dispatcher_ri.outbound', 'sphex.outbound')

        hops = [
            ['CONVERSATION:app2:conv2', 'default'],
            ['BILLING:OUTBOUND', 'default'],
            ['TRANSPORT_TAG:pool1:9012', 'default'],
        ]
        self.with_md(msg, tag=("pool1", "9012"), hops=hops, is_paid=True)
        self.assertEqual([msg], self.get_dispatched_outbound('sphex'))

    @inlineCallbacks
    def test_outbound_message_from_conversation_via_custom_endpoint(self):
        yield self.get_dispatcher()
        yield self.get_billing_dispatcher()
        msg = self.with_md(self.mkmsg_out(), conv=('app1', 'conv1'),
                           endpoint='other')

        yield self.dispatch_outbound(msg, 'app1')
        self.assert_rkeys_used(
            'app1.outbound', 'billing_dispatcher_ro.outbound',
            'billing_dispatcher_ri.outbound', 'sphex.outbound')

        hops = [
            ['CONVERSATION:app1:conv1', 'other'],
            ['BILLING:OUTBOUND', 'default'],
            ['TRANSPORT_TAG:pool1:5678', 'default'],
        ]
        self.with_md(msg, tag=("pool1", "5678"), endpoint='default',
                     hops=hops, is_paid=True)

        self.assertEqual([msg], self.get_dispatched_outbound('sphex'))

    @inlineCallbacks
    def test_outbound_message_from_router(self):
        yield self.get_dispatcher()
        yield self.get_billing_dispatcher()
        msg = self.with_md(self.mkmsg_out(), router=('router', 'router1'))
        yield self.dispatch_outbound(msg, 'router_ri')
        self.assert_rkeys_used(
            'router_ri.outbound', 'billing_dispatcher_ro.outbound',
            'billing_dispatcher_ri.outbound', 'sphex.outbound')

        hops = [
            ['ROUTER:router:router1:INBOUND', 'default'],
            ['BILLING:OUTBOUND', 'default'],
            ['TRANSPORT_TAG:pool1:1234', 'default'],
        ]
        self.with_md(msg, tag=("pool1", "1234"), hops=hops, is_paid=True)
        self.assertEqual([msg], self.get_dispatched_outbound('sphex'))

    @inlineCallbacks
    def test_outbound_message_from_router_via_custom_endpoint(self):
        yield self.get_dispatcher()
        yield self.get_billing_dispatcher()
        msg = self.with_md(self.mkmsg_out(), router=('router', 'router1'),
                           endpoint='other')

        yield self.dispatch_outbound(msg, 'router_ri')
        self.assert_rkeys_used(
            'router_ri.outbound', 'billing_dispatcher_ro.outbound',
            'billing_dispatcher_ri.outbound', 'sphex.outbound')

        hops = [
            ['ROUTER:router:router1:INBOUND', 'other'],
            ['BILLING:OUTBOUND', 'default'],
            ['TRANSPORT_TAG:pool1:5678', 'default'],
        ]
        self.with_md(msg, tag=("pool1", "5678"), endpoint='default',
                     hops=hops, is_paid=True)

        self.assertEqual([msg], self.get_dispatched_outbound('sphex'))
