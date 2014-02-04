from twisted.internet.defer import inlineCallbacks

from vumi.tests.helpers import VumiTestCase

from go.routers.app_multiplexer.vumi_app import ApplicationMultiplexer
from go.routers.tests.helpers import RouterWorkerHelper


class TestApplicationMultiplexerRouter(VumiTestCase):

    router_class = ApplicationMultiplexer

    @inlineCallbacks
    def setUp(self):
        self.router_helper = self.add_helper(
            RouterWorkerHelper(ApplicationMultiplexer)
        )
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
