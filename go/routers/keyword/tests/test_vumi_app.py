from twisted.internet.defer import inlineCallbacks

from vumi.tests.helpers import VumiTestCase

from go.vumitools.routing import RoutingMetadata
from go.routers.keyword.vumi_app import KeywordRouter
from go.routers.tests.helpers import RouterWorkerHelper


class TestKeywordRouter(VumiTestCase):

    router_class = KeywordRouter

    @inlineCallbacks
    def setUp(self):
        self.router_helper = self.add_helper(RouterWorkerHelper(KeywordRouter))
        self.router_worker = yield self.router_helper.get_router_worker({})

    @inlineCallbacks
    def assert_routed_inbound(self, content, router, expected_endpoint):
        msg = yield self.router_helper.ri.make_dispatch_inbound(
            content, router=router)
        emsg = msg.copy()
        emsg.set_routing_endpoint(expected_endpoint)
        rmsg = self.router_helper.ro.get_dispatched_inbound()[-1]
        self.assertEqual(emsg, rmsg)

    @inlineCallbacks
    def assert_routed_outbound(self, content, router, src_endpoint):
        msg = yield self.router_helper.ro.make_dispatch_outbound(
            content, router=router, routing_endpoint=src_endpoint)
        emsg = msg.copy()
        emsg.set_routing_endpoint('default')
        rmsg = self.router_helper.ri.get_dispatched_outbound()[-1]
        self.assertEqual(emsg, rmsg)

    @inlineCallbacks
    def assert_routed_event(self, router, expected_endpoint, hops):
        ack = self.router_helper.make_ack(router=router)
        self.set_event_hops(ack, hops)
        yield self.router_helper.ri.dispatch_event(ack)
        eevent = ack.copy()
        eevent.set_routing_endpoint(expected_endpoint)
        [revent] = self.router_helper.ro.get_dispatched_events()
        self.assertEqual(eevent, revent)

    def set_event_hops(self, event, outbound_hops, num_inbound_hops=1):
        rmeta = RoutingMetadata(event)
        rmeta.set_outbound_hops(outbound_hops)
        rev_hops = reversed(outbound_hops[-num_inbound_hops:])
        for outbound_src, outbound_dst in rev_hops:
            rmeta.push_hop(outbound_dst, outbound_src)

    @inlineCallbacks
    def test_start(self):
        router = yield self.router_helper.create_router()
        self.assertTrue(router.stopped())
        self.assertFalse(router.running())

        yield self.router_helper.start_router(router)
        router = yield self.router_helper.get_router(router.key)
        self.assertFalse(router.stopped())
        self.assertTrue(router.running())

    @inlineCallbacks
    def test_stop(self):
        router = yield self.router_helper.create_router(started=True)
        self.assertFalse(router.stopped())
        self.assertTrue(router.running())

        yield self.router_helper.stop_router(router)
        router = yield self.router_helper.get_router(router.key)
        self.assertTrue(router.stopped())
        self.assertFalse(router.running())

    @inlineCallbacks
    def test_no_messages_processed_while_stopped(self):
        router = yield self.router_helper.create_router()

        yield self.router_helper.ri.make_dispatch_inbound("foo", router=router)
        self.assertEqual([], self.router_helper.ro.get_dispatched_inbound())

        yield self.router_helper.ri.make_dispatch_ack(router=router)
        self.assertEqual([], self.router_helper.ro.get_dispatched_events())

        yield self.router_helper.ro.make_dispatch_outbound(
            "foo", router=router)
        self.assertEqual([], self.router_helper.ri.get_dispatched_outbound())
        [nack] = self.router_helper.ro.get_dispatched_events()
        self.assertEqual(nack['event_type'], 'nack')

    @inlineCallbacks
    def test_inbound_no_config(self):
        router = yield self.router_helper.create_router(started=True)
        yield self.assert_routed_inbound("foo bar", router, 'default')
        yield self.assert_routed_inbound("baz quux", router, 'default')

    @inlineCallbacks
    def test_inbound_keyword(self):
        router = yield self.router_helper.create_router(started=True, config={
            'keyword_endpoint_mapping': {
                'foo': 'app1',
                'abc123': 'app2',
            },
        })
        yield self.assert_routed_inbound("foo bar", router, 'app1')
        yield self.assert_routed_inbound("baz quux", router, 'default')
        yield self.assert_routed_inbound(" FoO bar", router, 'app1')
        yield self.assert_routed_inbound(" aBc123 baz", router, 'app2')

    @inlineCallbacks
    def test_outbound_no_config(self):
        router = yield self.router_helper.create_router(started=True)
        yield self.assert_routed_outbound("foo bar", router, 'default')
        yield self.assert_routed_outbound("baz quux", router, 'default')
        yield self.assert_routed_outbound("foo bar", router, 'app1')
        yield self.assert_routed_outbound("baz quux", router, 'app1')

    @inlineCallbacks
    def test_outbound(self):
        router = yield self.router_helper.create_router(started=True, config={
            'keyword_endpoint_mapping': {
                'foo': 'app1',
            },
        })
        yield self.assert_routed_outbound("foo bar", router, 'default')
        yield self.assert_routed_outbound("baz quux", router, 'default')
        yield self.assert_routed_outbound("foo bar", router, 'app1')
        yield self.assert_routed_outbound("baz quux", router, 'app1')

    @inlineCallbacks
    def test_event_default_to_default(self):
        router = yield self.router_helper.create_router(started=True, config={
            'keyword_endpoint_mapping': {
                'foo': 'app1',
            },
        })
        yield self.assert_routed_event(router, 'default', [
            [['app1', 'default'], ['kwr1', 'default']],
            [['kwr1', 'default'], ['sphex', 'default']],
        ])

    @inlineCallbacks
    def test_event_foo_to_default(self):
        router = yield self.router_helper.create_router(started=True, config={
            'keyword_endpoint_mapping': {
                'foo': 'app1',
            },
        })
        yield self.assert_routed_event(router, 'default', [
            [['app1', 'default'], ['kwr1', 'default']],
            [['kwr1', 'foo'], ['sphex', 'default']],
        ])

    @inlineCallbacks
    def test_event_default_to_foo(self):
        router = yield self.router_helper.create_router(started=True, config={
            'keyword_endpoint_mapping': {
                'foo': 'app1',
            },
        })
        yield self.assert_routed_event(router, 'foo', [
            [['app1', 'default'], ['kwr1', 'foo']],
            [['kwr1', 'default'], ['sphex', 'default']],
        ])

    @inlineCallbacks
    def test_event_foo_to_bar(self):
        router = yield self.router_helper.create_router(started=True, config={
            'keyword_endpoint_mapping': {
                'foo': 'app1',
            },
        })
        yield self.assert_routed_event(router, 'bar', [
            [['app1', 'default'], ['kwr1', 'bar']],
            [['kwr1', 'foo'], ['sphex', 'default']],
        ])
