from twisted.internet.defer import inlineCallbacks

from vumi.tests.helpers import VumiTestCase

from go.routers.application_multiplexer.vumi_app import ApplicationMultiplexer
from go.routers.tests.helpers import RouterWorkerHelper
from vumi.tests.helpers import PersistenceHelper, MessageHelper


class TestApplicationMultiplexerRouter(VumiTestCase):

    router_class = ApplicationMultiplexer

    @inlineCallbacks
    def setUp(self):
        self.router_helper = self.add_helper(
            RouterWorkerHelper(ApplicationMultiplexer))

        self.msg_helper = yield self.add_helper(MessageHelper())
        self.persistence_helper = yield self.add_helper(PersistenceHelper())
        self.parent_redis = yield self.persistence_helper.get_redis_manager()
        self.router_worker = yield self.router_helper.get_router_worker({
            'worker_name': 'application_multiplexer',
            'redis_manager': {
                'FAKE_REDIS': self.parent_redis,
                'key_prefix': self.parent_redis.get_key_prefix(),
            }
        })

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

    def test_get_menu_choice(self):
        # good
        msg = self.msg_helper.make_inbound(content='3 ')
        choice = self.router_worker.get_menu_choice(msg, (1, 4))
        self.assertEqual(choice, 3)

        # bad - out of range
        choice = self.router_worker.get_menu_choice(msg, (1, 2))
        self.assertEqual(choice, None)

        # bad - non-numeric input
        msg = self.msg_helper.make_inbound(content='Foo ')
        choice = self.router_worker.get_menu_choice(msg, (1, 2))
        self.assertEqual(choice, None)

    def test_scan_for_keywords(self):
        config = self.router_worker.config
        msg = self.msg_helper.make_inbound(content=':menu')
        self.assertTrue(self.router_worker.scan_for_keywords(
            config,
            msg, (':menu',)))
        msg = self.msg_helper.make_inbound(content='Foo bar baz')
        self.assertFalse(self.router_worker.scan_for_keywords(
            config,
            msg, (':menu',)))

    def test_create_menu(self):
        config = self.router_worker.config.copy()
        config.update({
            'menu_title': {'content': 'Please select a choice'},
            'entries': [
                {
                    'label': 'Flappy Bird',
                    'endpoint': 'flappy-bird',
                },
                {
                    'label': 'Mama',
                    'endpoint': 'mama',
                }
            ]
        })
        config = self.router_worker.CONFIG_CLASS(config)

        text = self.router_worker.create_menu(config)
        self.assertEqual(text,
                         'Please select a choice\n1) Flappy Bird\n2) Mama')
