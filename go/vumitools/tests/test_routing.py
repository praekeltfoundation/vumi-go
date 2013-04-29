from twisted.internet.defer import inlineCallbacks, returnValue

from go.vumitools.routing import AccountRoutingTableDispatcher
from go.vumitools.tests.utils import AppWorkerTestCase


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
            "pool1:1234": {"default": ["app1:conv1", "default"]},
            "pool1:5678": {"default": ["app1:conv1", "other"]},
            "pool1:9012": {"default": ["app2:conv2", "default"]},
            # Application side
            "app1:conv1": {
                "default": ["pool1:1234", "default"],
                "other": ["pool1:5678", "default"],
            },
            "app2:conv2": {
                "default": ["pool1:9012", "default"],
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
            "receive_inbound_connectors": ["sphex"],
            "receive_outbound_connectors": ["app1", "app2", "optout"],
            "metrics_prefix": "foo",
            "opt_out_connector": "optout",
        }
        config.update(config_extras)
        dispatcher = yield self.get_worker(
            self.mk_config(config), AccountRoutingTableDispatcher)
        returnValue(dispatcher)

    def with_endpoint(self, msg, endpoint=None):
        if endpoint is None:
            endpoint = msg.get_routing_endpoint()
        msg.set_routing_endpoint(endpoint)
        return msg

    def with_tag(self, msg, tag, ep=None):
        """Convenience method for adding a tag to a message."""
        tag_metadata = msg['helper_metadata'].setdefault('tag', {})
        # convert tag to list so that msg == json.loads(json.dumps(msg))
        tag_metadata['tag'] = list(tag)
        return self.with_endpoint(msg, ep)

    def with_conv(self, msg, conv_type, conv_key, ep=None):
        """Convenience method for adding conversation data to a message."""
        go_metadata = msg['helper_metadata'].setdefault('go', {})
        go_metadata.update({
            'user_account': self.user_account_key,
            'conversation_type': conv_type,
            'conversation_key': conv_key,
        })
        return self.with_endpoint(msg, ep)

    def assert_rkeys_used(self, *rkeys):
        self.assertEqual(set(rkeys), set(self._amqp.dispatched['vumi'].keys()))

    @inlineCallbacks
    def test_inbound_message_routing(self):
        yield self.get_dispatcher()
        msg = self.with_tag(self.mkmsg_in(), ("pool1", "1234"))
        yield self.dispatch_inbound(msg, 'sphex')
        self.assert_rkeys_used('sphex.inbound', 'app1.inbound')
        self.assertEqual(
            [self.with_conv(msg, 'app1', 'conv1')],
            self.get_dispatched_inbound('app1'))

        self.clear_all_dispatched()
        msg = self.with_tag(self.mkmsg_in(), ("pool1", "5678"))
        yield self.dispatch_inbound(msg, 'sphex')
        self.assert_rkeys_used('sphex.inbound', 'app1.inbound')
        self.assertEqual(
            [self.with_conv(msg, 'app1', 'conv1', ep='other')],
            self.get_dispatched_inbound('app1'))

        self.clear_all_dispatched()
        msg = self.with_tag(self.mkmsg_in(), ("pool1", "9012"))
        yield self.dispatch_inbound(msg, 'sphex')
        self.assert_rkeys_used('sphex.inbound', 'app2.inbound')
        self.assertEqual(
            [self.with_conv(msg, 'app2', 'conv2')],
            self.get_dispatched_inbound('app2'))

    @inlineCallbacks
    def test_opt_out_message_routing(self):
        yield self.get_dispatcher()
        tag = ("pool1", "1234")
        msg = self.with_tag(self.mkmsg_in(), tag)
        msg['helper_metadata']['go'] = {
            'user_account': self.user_account_key,
        }
        msg['helper_metadata']['optout'] = {'optout': True}
        yield self.dispatch_inbound(msg, 'sphex')
        self.assert_rkeys_used('sphex.inbound', 'optout.inbound')
        self.assertEqual(
            [self.with_tag(msg, tag)],
            self.get_dispatched_inbound('optout'))

    @inlineCallbacks
    def test_outbound_message_routing(self):
        yield self.get_dispatcher()
        msg = self.with_conv(self.mkmsg_out(), 'app1', 'conv1')
        yield self.dispatch_outbound(msg, 'app1')
        self.assert_rkeys_used('app1.outbound', 'sphex.outbound')
        self.assertEqual(
            [self.with_tag(msg, ("pool1", "1234"))],
            self.get_dispatched_outbound('sphex'))

        self.clear_all_dispatched()
        msg = self.with_conv(self.mkmsg_out(), 'app2', 'conv2')
        yield self.dispatch_outbound(msg, 'app2')
        self.assert_rkeys_used('app2.outbound', 'sphex.outbound')
        self.assertEqual(
            [self.with_tag(msg, ("pool1", "9012"))],
            self.get_dispatched_outbound('sphex'))

        self.clear_all_dispatched()
        msg = self.with_conv(self.mkmsg_out(), 'app1', 'conv1', ep='other')
        yield self.dispatch_outbound(msg, 'app1')
        self.assert_rkeys_used('app1.outbound', 'sphex.outbound')
        self.assertEqual(
            [self.with_tag(msg, ("pool1", "5678"), ep='default')],
            self.get_dispatched_outbound('sphex'))

    @inlineCallbacks
    def mk_msg_ack(self, conv_type, conv_key, ep=None):
        "Create and store an outbound message, then create an ack for it."
        msg = self.with_conv(self.mkmsg_out(), conv_type, conv_key, ep=ep)
        yield self.vumi_api.mdb.add_outbound_message(msg)

        ack = self.mkmsg_ack(
            user_message_id=msg['message_id'])

        returnValue((msg, ack))

    @inlineCallbacks
    def test_event_routing(self):
        dispatcher = yield self.get_dispatcher()
        self.vumi_api = dispatcher.vumi_api

        msg, ack = yield self.mk_msg_ack('app1', 'conv1')
        yield self.dispatch_event(ack, 'sphex')
        self.assert_rkeys_used('sphex.event', 'app1.event')
        self.assertEqual(
            [self.with_endpoint(ack)],
            self.get_dispatched_events('app1'))

        self.clear_all_dispatched()
        msg, ack = yield self.mk_msg_ack('app1', 'conv1', ep='other')
        yield self.dispatch_event(ack, 'sphex')
        self.assert_rkeys_used('sphex.event', 'app1.event')
        self.assertEqual(
            [self.with_endpoint(ack)],
            self.get_dispatched_events('app1'))

        self.clear_all_dispatched()
        msg, ack = yield self.mk_msg_ack('app2', 'conv2')
        yield self.dispatch_event(ack, 'sphex')
        self.assert_rkeys_used('sphex.event', 'app2.event')
        self.assertEqual(
            [self.with_endpoint(ack)],
            self.get_dispatched_events('app2'))
