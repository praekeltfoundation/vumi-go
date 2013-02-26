from twisted.internet.defer import inlineCallbacks, returnValue

from go.vumitools.routing import AccountRoutingTableDispatcher
from go.vumitools.tests.utils import AppWorkerTestCase


class TestRoutingTableDispatcher(AppWorkerTestCase):
    timeout = 1

    @inlineCallbacks
    def get_dispatcher(self, **config_extras):
        config = {
            "receive_inbound_connectors": ["transport1"],
            "receive_outbound_connectors": ["app1", "app2"],
            "routing_table": {
                "transport1": {
                    "pool1:1234:default": ["app1", "conv1:default"],
                    "pool1:5678:default": ["app1", "conv1:other"],
                    "pool1:9012:default": ["app2", "conv2:default"],
                },
                "app1": {
                    "conv1:default": ["transport1", "pool1:1234:default"],
                    "conv1:other": ["transport1", "pool1:5678:default"],
                },
                "app2": {
                    "conv2:default": ["transport1", "pool1:9012:default"],
                },
            },
            "metrics_prefix": "foo",
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
        yield self.dispatch_inbound(msg, 'transport1')
        self.assert_rkeys_used('transport1.inbound', 'app1.inbound')
        self.assertEqual(
            [self.with_conv(msg, 'app1', 'conv1')],
            self.get_dispatched_inbound('app1'))

        self.clear_all_dispatched()
        msg = self.with_tag(self.mkmsg_in(), ("pool1", "5678"))
        yield self.dispatch_inbound(msg, 'transport1')
        self.assert_rkeys_used('transport1.inbound', 'app1.inbound')
        self.assertEqual(
            [self.with_conv(msg, 'app1', 'conv1', ep='other')],
            self.get_dispatched_inbound('app1'))

        self.clear_all_dispatched()
        msg = self.with_tag(self.mkmsg_in(), ("pool1", "9012"))
        yield self.dispatch_inbound(msg, 'transport1')
        self.assert_rkeys_used('transport1.inbound', 'app2.inbound')
        self.assertEqual(
            [self.with_conv(msg, 'app2', 'conv2')],
            self.get_dispatched_inbound('app2'))

    @inlineCallbacks
    def test_outbound_message_routing(self):
        yield self.get_dispatcher()
        msg = self.with_conv(self.mkmsg_in(), 'app1', 'conv1')
        yield self.dispatch_outbound(msg, 'app1')
        self.assert_rkeys_used('app1.outbound', 'transport1.outbound')
        self.assertEqual(
            [self.with_tag(msg, ("pool1", "1234"))],
            self.get_dispatched_outbound('transport1'))

        self.clear_all_dispatched()
        msg = self.with_conv(self.mkmsg_in(), 'app2', 'conv2')
        yield self.dispatch_outbound(msg, 'app2')
        self.assert_rkeys_used('app2.outbound', 'transport1.outbound')
        self.assertEqual(
            [self.with_tag(msg, ("pool1", "9012"))],
            self.get_dispatched_outbound('transport1'))

        self.clear_all_dispatched()
        msg = self.with_conv(self.mkmsg_in(), 'app1', 'conv1', ep='other')
        yield self.dispatch_outbound(msg, 'app1')
        self.assert_rkeys_used('app1.outbound', 'transport1.outbound')
        self.assertEqual(
            [self.with_tag(msg, ("pool1", "5678"), ep='default')],
            self.get_dispatched_outbound('transport1'))
