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
        msg.set_routing_endpoint(endpoint)
        return msg

    def with_tag(self, msg, tag):
        """Convenience method for adding a tag to a message."""
        tag_metadata = msg['helper_metadata'].setdefault('tag', {})
        # convert tag to list so that msg == json.loads(json.dumps(msg))
        tag_metadata['tag'] = list(tag)
        return msg

    def assert_rkeys_used(self, *rkeys):
        self.assertEqual(set(rkeys), set(self._amqp.dispatched['vumi'].keys()))

    @inlineCallbacks
    def test_inbound_message_routing(self):
        yield self.get_dispatcher()
        msg = self.with_tag(self.mkmsg_in(), ("pool1", "1234"))
        yield self.dispatch_inbound(msg, 'transport1')
        self.assert_rkeys_used('transport1.inbound', 'app1.inbound')
        self.assertEqual(
            [self.with_endpoint(msg)], self.get_dispatched_inbound('app1'))

        self.clear_all_dispatched()
        msg = self.with_tag(self.mkmsg_in(), ("pool1", "5678"))
        yield self.dispatch_inbound(msg, 'transport1')
        self.assert_rkeys_used('transport1.inbound', 'app1.inbound')
        self.assertEqual(
            [self.with_endpoint(msg, 'other')],
            self.get_dispatched_inbound('app1'))

        self.clear_all_dispatched()
        msg = self.with_tag(self.mkmsg_in(), ("pool1", "9012"))
        yield self.dispatch_inbound(msg, 'transport1')
        self.assert_rkeys_used('transport1.inbound', 'app2.inbound')
        self.assertEqual(
            [self.with_endpoint(msg)], self.get_dispatched_inbound('app2'))

    @inlineCallbacks
    def test_outbound_message_routing(self):
        yield self.get_dispatcher()
        msg = self.mkmsg_in()
        yield self.dispatch_outbound(msg, 'app1')
        self.assert_rkeys_used('app1.outbound', 'transport1.outbound')
        self.assertEqual(
            [self.with_endpoint(msg)],
            self.get_dispatched_outbound('transport1'))

        self.clear_all_dispatched()
        msg = self.mkmsg_in()
        yield self.dispatch_outbound(msg, 'app2')
        self.assert_rkeys_used('app2.outbound', 'transport2.outbound')
        self.assertEqual(
            [self.with_endpoint(msg)],
            self.get_dispatched_outbound('transport2'))

        self.clear_all_dispatched()
        msg = self.mkmsg_in()
        msg.set_routing_endpoint('ep2')
        yield self.dispatch_outbound(msg, 'app1')
        self.assert_rkeys_used('app1.outbound', 'transport2.outbound')
        self.assertEqual(
            [self.with_endpoint(msg)],
            self.get_dispatched_outbound('transport2'))

    # @inlineCallbacks
    # def test_inbound_event_routing(self):
    #     yield self.get_dispatcher()
    #     msg = self.mkmsg_ack()
    #     yield self.dispatch_event(msg, 'transport1')
    #     self.assert_rkeys_used('transport1.event', 'app1.event')
    #     self.assertEqual(
    #         [self.with_endpoint(msg)], self.get_dispatched_events('app1'))

    #     self.clear_all_dispatched()
    #     msg = self.mkmsg_ack()
    #     yield self.dispatch_event(msg, 'transport2')
    #     self.assert_rkeys_used('transport2.event', 'app2.event')
    #     self.assertEqual(
    #         [self.with_endpoint(msg)], self.get_dispatched_events('app2'))

    #     self.clear_all_dispatched()
    #     msg = self.mkmsg_ack()
    #     msg.set_routing_endpoint('ep1')
    #     yield self.dispatch_event(msg, 'transport2')
    #     self.assert_rkeys_used('transport2.event', 'app1.event')
    #     self.assertEqual(
    #         [self.with_endpoint(msg, 'ep1')], self.get_dispatched_events('app1'))
