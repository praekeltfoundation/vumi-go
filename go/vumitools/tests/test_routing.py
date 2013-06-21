from twisted.internet.defer import inlineCallbacks, returnValue

from go.vumitools.routing import AccountRoutingTableDispatcher
from go.vumitools.tests.utils import AppWorkerTestCase
from go.vumitools.utils import MessageMetadataHelper


class TestRoutingTableDispatcher(AppWorkerTestCase):
    timeout = 1

    @inlineCallbacks
    def setUp(self):
        yield super(TestRoutingTableDispatcher, self).setUp()
        self.dispatcher = yield self.get_dispatcher()
        self.vumi_api = self.dispatcher.vumi_api

        user_account = yield self.mk_user(self.vumi_api, u'testuser')
        user_account.routing_table = {
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
            "ROUTING_BLOCK:router:router1:INBOUND": {
                "default": ["TRANSPORT_TAG:pool1:1234", "default"],
                "other": ["TRANSPORT_TAG:pool1:5678", "default"],
            },
            # Router inbound
            "ROUTING_BLOCK:router:router1:OUTBOUND": {
                "default": ["CONVERSATION:app1:conv1", "default"],
                "other": ["CONVERSATION:app2:conv2", "yet-another"],
            },
        }
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
                "sphex", "router_ro",
            ],
            "receive_outbound_connectors": [
                "app1", "app2", "router_ri", "optout",
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
            "opt_out_connector": "optout",
        }
        config.update(config_extras)
        dispatcher = yield self.get_worker(
            self.mk_config(config), AccountRoutingTableDispatcher)
        returnValue(dispatcher)

    def with_md(self, msg, user_account=None, conv=None, router=None,
                endpoint=None, tag=None, hops=None):
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
        if hops is not None:
            routes = msg['routing_metadata'].setdefault('hops', [])
            routes[:] = hops
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
    def test_inbound_message_from_transport(self):
        yield self.get_dispatcher()
        msg = self.with_md(self.mkmsg_in(), tag=("pool1", "1234"))
        yield self.dispatch_inbound(msg, 'sphex')
        self.assert_rkeys_used('sphex.inbound', 'app1.inbound')
        self.with_md(msg, conv=('app1', 'conv1'),
                     hops=[['CONVERSATION:app1:conv1', 'default']])
        self.assertEqual([msg], self.get_dispatched_inbound('app1'))

        self.clear_all_dispatched()
        msg = self.with_md(self.mkmsg_in(), tag=("pool1", "5678"))
        yield self.dispatch_inbound(msg, 'sphex')
        self.assert_rkeys_used('sphex.inbound', 'app1.inbound')
        self.with_md(msg, conv=('app1', 'conv1'), endpoint='other',
                     hops=[['CONVERSATION:app1:conv1', 'other']])
        self.assertEqual([msg], self.get_dispatched_inbound('app1'))

        self.clear_all_dispatched()
        msg = self.with_md(self.mkmsg_in(), tag=("pool1", "9012"))
        yield self.dispatch_inbound(msg, 'sphex')
        self.assert_rkeys_used('sphex.inbound', 'app2.inbound')
        self.with_md(msg, conv=('app2', 'conv2'),
                     hops=[['CONVERSATION:app2:conv2', 'default']])
        self.assertEqual([msg], self.get_dispatched_inbound('app2'))

    @inlineCallbacks
    def test_inbound_message_from_transport_to_optout(self):
        yield self.get_dispatcher()
        tag = ("pool1", "1234")
        msg = self.with_md(self.mkmsg_in(), tag=tag)
        msg['helper_metadata']['optout'] = {'optout': True}
        yield self.dispatch_inbound(msg, 'sphex')
        self.assert_rkeys_used('sphex.inbound', 'optout.inbound')
        self.with_md(msg, user_account=self.user_account_key,
                     hops=[['OPT_OUT', 'default']])
        self.assertEqual([msg], self.get_dispatched_inbound('optout'))

    @inlineCallbacks
    def test_inbound_message_from_router(self):
        yield self.get_dispatcher()
        msg = self.with_md(self.mkmsg_out(), router=('router', 'router1'))
        yield self.dispatch_inbound(msg, 'router_ro')
        self.assert_rkeys_used('router_ro.inbound', 'app1.inbound')
        self.with_md(msg, conv=("app1", "conv1"),
                     hops=[['CONVERSATION:app1:conv1', 'default']])
        self.assertEqual([msg], self.get_dispatched_inbound('app1'))

        self.clear_all_dispatched()
        msg = self.with_md(self.mkmsg_out(), router=('router', 'router1'),
                           endpoint='other')
        yield self.dispatch_inbound(msg, 'router_ro')
        self.assert_rkeys_used('router_ro.inbound', 'app2.inbound')
        self.with_md(msg, conv=("app2", "conv2"), endpoint='yet-another',
                     hops=[['CONVERSATION:app2:conv2', 'yet-another']])
        self.assertEqual([msg], self.get_dispatched_inbound('app2'))

    @inlineCallbacks
    def test_outbound_message_from_optout_to_transport(self):
        yield self.get_dispatcher()
        tag = ("pool1", "1234")
        msg, reply = yield self.mk_msg_reply(tag=tag)
        yield self.dispatch_outbound(reply, 'optout')
        self.assert_rkeys_used('optout.outbound', 'sphex.outbound')
        self.with_md(reply, tag=tag, user_account=self.user_account_key,
                     hops=[['TRANSPORT_TAG:pool1:1234', 'default']])
        self.assertEqual([reply], self.get_dispatched_outbound('sphex'))

    @inlineCallbacks
    def test_outbound_message_from_converation(self):
        yield self.get_dispatcher()
        msg = self.with_md(self.mkmsg_out(), conv=('app1', 'conv1'))
        yield self.dispatch_outbound(msg, 'app1')
        self.assert_rkeys_used('app1.outbound', 'sphex.outbound')
        self.with_md(msg, tag=("pool1", "1234"),
                     hops=[['TRANSPORT_TAG:pool1:1234', 'default']])
        self.assertEqual([msg], self.get_dispatched_outbound('sphex'))

        self.clear_all_dispatched()
        msg = self.with_md(self.mkmsg_out(), conv=('app2', 'conv2'))
        yield self.dispatch_outbound(msg, 'app2')
        self.assert_rkeys_used('app2.outbound', 'sphex.outbound')
        self.with_md(msg, tag=("pool1", "9012"),
                     hops=[['TRANSPORT_TAG:pool1:9012', 'default']])
        self.assertEqual([msg], self.get_dispatched_outbound('sphex'))

        self.clear_all_dispatched()
        msg = self.with_md(self.mkmsg_out(), conv=('app1', 'conv1'),
                           endpoint='other')
        yield self.dispatch_outbound(msg, 'app1')
        self.assert_rkeys_used('app1.outbound', 'sphex.outbound')
        self.with_md(msg, tag=("pool1", "5678"), endpoint='default',
                     hops=[['TRANSPORT_TAG:pool1:5678', 'default']])
        self.assertEqual([msg], self.get_dispatched_outbound('sphex'))

    @inlineCallbacks
    def test_outbound_message_from_router(self):
        yield self.get_dispatcher()
        msg = self.with_md(self.mkmsg_out(), router=('router', 'router1'))
        yield self.dispatch_outbound(msg, 'router_ri')
        self.assert_rkeys_used('router_ri.outbound', 'sphex.outbound')
        self.with_md(msg, tag=("pool1", "1234"),
                     hops=[['TRANSPORT_TAG:pool1:1234', 'default']])
        self.assertEqual([msg], self.get_dispatched_outbound('sphex'))

        self.clear_all_dispatched()
        msg = self.with_md(self.mkmsg_out(), router=('router', 'router1'),
                           endpoint='other')
        yield self.dispatch_outbound(msg, 'router_ri')
        self.assert_rkeys_used('router_ri.outbound', 'sphex.outbound')
        self.with_md(msg, tag=("pool1", "5678"), endpoint='default',
                     hops=[['TRANSPORT_TAG:pool1:5678', 'default']])
        self.assertEqual([msg], self.get_dispatched_outbound('sphex'))

    @inlineCallbacks
    def test_event_routing(self):
        dispatcher = yield self.get_dispatcher()
        self.vumi_api = dispatcher.vumi_api

        msg, ack = yield self.mk_msg_ack(hops=[
            ['CONVERSATION:app1:conv1', 'default'],
        ])
        yield self.dispatch_event(ack, 'sphex')
        self.assert_rkeys_used('sphex.event', 'app1.event')
        self.with_md(ack, hops=[['CONVERSATION:app1:conv1', 'default']])
        self.assertEqual([ack], self.get_dispatched_events('app1'))

        self.clear_all_dispatched()
        msg, ack = yield self.mk_msg_ack(endpoint='other', hops=[
            ['CONVERSATION:app1:conv1', 'other'],
        ])
        yield self.dispatch_event(ack, 'sphex')
        self.assert_rkeys_used('sphex.event', 'app1.event')
        self.with_md(ack, endpoint='other',
                     hops=[['CONVERSATION:app1:conv1', 'other']])
        self.assertEqual([ack], self.get_dispatched_events('app1'))

        self.clear_all_dispatched()
        msg, ack = yield self.mk_msg_ack(hops=[
            ['CONVERSATION:app2:conv2', 'default'],
        ])
        yield self.dispatch_event(ack, 'sphex')
        self.assert_rkeys_used('sphex.event', 'app2.event')
        self.with_md(ack, hops=[['CONVERSATION:app2:conv2', 'default']])
        self.assertEqual([ack], self.get_dispatched_events('app2'))
