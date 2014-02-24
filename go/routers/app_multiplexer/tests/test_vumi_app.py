import copy
import json

from twisted.internet.defer import inlineCallbacks

from vumi.tests.helpers import VumiTestCase
from go.routers.app_multiplexer.vumi_app import ApplicationMultiplexer
from go.routers.tests.helpers import RouterWorkerHelper


def raise_error(*args, **kw):
    raise RuntimeError("An anomaly has been detected")


class TestApplicationMultiplexerRouter(VumiTestCase):

    router_class = ApplicationMultiplexer

    ROUTER_CONFIG = {
        'invalid_input_message': 'Bad choice.\n1) Try Again',
        'error_message': 'Oops! Sorry!',
        'keyword': ':menu',
        'entries': [
            {
                'label': 'Flappy Bird',
                'endpoint': 'flappy-bird',
            },
        ]
    }

    @inlineCallbacks
    def setUp(self):
        self.router_helper = self.add_helper(
            RouterWorkerHelper(ApplicationMultiplexer))
        self.router_worker = yield self.router_helper.get_router_worker({})

    def setup_session(self, user_id, data):
        return self.router_worker.session_manager.create_session(
            user_id,
            **data
        )

    @inlineCallbacks
    def assert_session_state(self, user_id, expected_session):
        session = yield self.router_worker.session_manager.load_session(
            user_id)
        if 'created_at' in session:
            del session['created_at']
        self.assertEqual(session, expected_session,
                         msg="Unexpected session data")

    def dynamic_config(self, fields):
        config = self.router_worker.config.copy()
        config.update(fields)
        return config

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
    def test_state_start_to_select(self):
        router = yield self.router_helper.create_router(
            started=True,
            config=self.ROUTER_CONFIG
        )
        # msg sent from user
        yield self.router_helper.ri.make_dispatch_inbound(
            None,
            router=router,
            from_addr='123')

        # assert that the user received a response
        [msg] = self.router_helper.ri.get_dispatched_outbound()
        self.assertEqual(msg['content'],
                         'Please select a choice.\n1) Flappy Bird')
        # assert that session data updated correctly
        yield self.assert_session_state('123', {
            'state': ApplicationMultiplexer.STATE_SELECT,
            'endpoints': '["flappy-bird"]',
        })

    @inlineCallbacks
    def test_state_select_to_selected(self):
        router = yield self.router_helper.create_router(
            started=True,
            config=self.ROUTER_CONFIG
        )

        yield self.setup_session('123', {
            'state': ApplicationMultiplexer.STATE_SELECT,
            'endpoints': '["flappy-bird"]',
        })

        # msg sent from user
        msg = yield self.router_helper.ri.make_dispatch_inbound(
            '1',
            router=router,
            from_addr='123',
            session_event='resume'
        )

        # assert that message is forwarded to application
        [msg] = self.router_helper.ro.get_dispatched_inbound()
        self.assertEqual(msg['content'], None)
        self.assertEqual(msg['session_event'], 'new')

        # application sends reply
        yield self.router_helper.ro.make_dispatch_reply(msg, 'Flappy Flappy!')

        # assert that the user received a response
        [msg] = self.router_helper.ri.get_dispatched_outbound()
        self.assertEqual(msg['content'],
                         'Flappy Flappy!')

        yield self.assert_session_state('123', {
            'state': ApplicationMultiplexer.STATE_SELECTED,
            'active_endpoint': 'flappy-bird',
            'endpoints': '["flappy-bird"]',
        })

    @inlineCallbacks
    def test_state_selected_to_selected(self):
        router = yield self.router_helper.create_router(
            started=True,
            config=self.ROUTER_CONFIG
        )

        yield self.setup_session('123', {
            'state': ApplicationMultiplexer.STATE_SELECTED,
            'active_endpoint': 'flappy-bird',
            'endpoints': '["flappy-bird"]',
        })

        # msg sent from user
        msg = yield self.router_helper.ri.make_dispatch_inbound(
            'Up!',
            router=router,
            from_addr='123',
            session_event='resume'
        )

        # assert that message is forwarded to application
        [msg] = self.router_helper.ro.get_dispatched_inbound()
        self.assertEqual(msg['content'], 'Up!')
        self.assertEqual(msg['session_event'], 'resume')

        # application sends reply
        yield self.router_helper.ro.make_dispatch_reply(
            msg,
            'Game Over!\n1) Try Again!'
        )

        # assert that the user received a response
        [msg] = self.router_helper.ri.get_dispatched_outbound()
        self.assertEqual(msg['content'],
                         'Game Over!\n1) Try Again!')

        yield self.assert_session_state('123', {
            'state': ApplicationMultiplexer.STATE_SELECTED,
            'active_endpoint': 'flappy-bird',
            'endpoints': '["flappy-bird"]',
        })

    @inlineCallbacks
    def test_state_selected_to_select(self):
        router = yield self.router_helper.create_router(
            started=True,
            config=self.ROUTER_CONFIG
        )

        yield self.setup_session('123', {
            'state': ApplicationMultiplexer.STATE_SELECTED,
            'active_endpoint': 'flappy-bird',
            'endpoints': '["flappy-bird"]',
        })

        # msg sent from user
        msg = yield self.router_helper.ri.make_dispatch_inbound(
            ':menu',
            router=router,
            from_addr='123',
            session_event='resume'
        )

        # assert that a close message is forwarded to application
        [msg] = self.router_helper.ro.get_dispatched_inbound()
        self.assertEqual(msg['content'], None)
        self.assertEqual(msg['session_event'], 'close')

         # assert that the user received a response
        [msg] = self.router_helper.ri.get_dispatched_outbound()
        self.assertEqual(msg['content'],
                         'Please select a choice.\n1) Flappy Bird')

        yield self.assert_session_state('123', {
            'state': ApplicationMultiplexer.STATE_SELECT,
            'active_endpoint': 'None',
            'endpoints': '["flappy-bird"]',
        })

    @inlineCallbacks
    def test_state_select_to_bad_input(self):
        router = yield self.router_helper.create_router(
            started=True,
            config=self.ROUTER_CONFIG
        )

        yield self.setup_session('123', {
            'state': ApplicationMultiplexer.STATE_SELECT,
            'endpoints': '["flappy-bird"]',
        })

        # msg sent from user
        msg = yield self.router_helper.ri.make_dispatch_inbound(
            'foo',
            router=router,
            from_addr='123',
            session_event='resume'
        )

         # assert that the user received a response
        [msg] = self.router_helper.ri.get_dispatched_outbound()
        self.assertEqual(msg['content'],
                         'Bad choice.\n1) Try Again')

        yield self.assert_session_state('123', {
            'state': ApplicationMultiplexer.STATE_BAD_INPUT,
            'endpoints': '["flappy-bird"]',
        })

    @inlineCallbacks
    def test_state_bad_input_to_bad_input(self):
        router = yield self.router_helper.create_router(
            started=True,
            config=self.ROUTER_CONFIG
        )

        yield self.setup_session('123', {
            'state': ApplicationMultiplexer.STATE_BAD_INPUT,
            'endpoints': '["flappy-bird"]',
        })

        # msg sent from user
        msg = yield self.router_helper.ri.make_dispatch_inbound(
            'foo',
            router=router,
            from_addr='123',
            session_event='resume'
        )

         # assert that the user received a response
        [msg] = self.router_helper.ri.get_dispatched_outbound()
        self.assertEqual(msg['content'],
                         'Bad choice.\n1) Try Again')

        yield self.assert_session_state('123', {
            'state': ApplicationMultiplexer.STATE_BAD_INPUT,
            'endpoints': '["flappy-bird"]',
        })

    @inlineCallbacks
    def test_state_bad_input_to_select(self):
        router = yield self.router_helper.create_router(
            started=True,
            config=self.ROUTER_CONFIG
        )

        yield self.setup_session('123', {
            'state': ApplicationMultiplexer.STATE_BAD_INPUT,
            'endpoints': '["flappy-bird"]',
        })

        # msg sent from user
        msg = yield self.router_helper.ri.make_dispatch_inbound(
            '1',
            router=router,
            from_addr='123',
            session_event='resume'
        )

         # assert that the user received a response
        [msg] = self.router_helper.ri.get_dispatched_outbound()
        self.assertEqual(msg['content'],
                         'Please select a choice.\n1) Flappy Bird')

        yield self.assert_session_state('123', {
            'state': ApplicationMultiplexer.STATE_SELECT,
            'endpoints': '["flappy-bird"]',
        })

    @inlineCallbacks
    def test_runtime_exception(self):
        """
        Verifies that the worker handles an arbitrary runtime error gracefully,
        and sends an appropriate error message back to the user
        """
        router = yield self.router_helper.create_router(
            started=True,
            config=self.ROUTER_CONFIG
        )

        # Make worker.target_endpoints raise an exception
        self.patch(self.router_worker,
                   'target_endpoints',
                   raise_error)

        yield self.setup_session('123', {
            'state': ApplicationMultiplexer.STATE_SELECTED,
            'active_endpoint': 'flappy-bird',
            'endpoints': '["flappy-bird"]',
        })

        # msg sent from user
        msg = yield self.router_helper.ri.make_dispatch_inbound(
            'Up!',
            router=router,
            from_addr='123',
            session_event='resume'
        )
        # assert that the user received a response
        [msg] = self.router_helper.ri.get_dispatched_outbound()
        self.assertEqual(msg['content'],
                         'Oops! Sorry!')

        yield self.assert_session_state('123', {})

        errors = self.flushLoggedErrors(RuntimeError)
        self.assertEqual(len(errors), 1)

    @inlineCallbacks
    def test_session_invalidation(self):
        """
        Verify that the router gracefully handles a configuration
        update while there is an active user session.

        A session is aborted if there is no longer an attached endpoint
        to which it refers.
        """
        config = copy.deepcopy(self.ROUTER_CONFIG)
        config['entries'][0]['endpoint'] = 'mama'
        router = yield self.router_helper.create_router(
            started=True,
            config=config
        )
        yield self.setup_session('123', {
            'state': ApplicationMultiplexer.STATE_SELECTED,
            'active_endpoint': 'flappy-bird',
            'endpoints': '["flappy-bird"]',
        })

        # msg sent from user
        msg = yield self.router_helper.ri.make_dispatch_inbound(
            'Up!',
            router=router,
            from_addr='123',
            session_event='resume'
        )
        # assert that the user received a response
        [msg] = self.router_helper.ri.get_dispatched_outbound()
        self.assertEqual(msg['content'],
                         'Oops! Sorry!')
        yield self.assert_session_state('123', {})

    def test_get_menu_choice(self):
        # good
        msg = self.router_helper.make_inbound(content='3 ')
        choice = self.router_worker.get_menu_choice(msg, (1, 4))
        self.assertEqual(choice, 3)

        # bad - out of range
        choice = self.router_worker.get_menu_choice(msg, (1, 2))
        self.assertEqual(choice, None)

        # bad - non-numeric input
        msg = self.router_helper.make_inbound(content='Foo ')
        choice = self.router_worker.get_menu_choice(msg, (1, 2))
        self.assertEqual(choice, None)

    def test_scan_for_keywords(self):
        config = self.dynamic_config({
            'keyword': ':menu'
        })
        msg = self.router_helper.make_inbound(content=':menu')
        self.assertTrue(self.router_worker.scan_for_keywords(
            config,
            msg, (':menu',)))
        msg = self.router_helper.make_inbound(content='Foo bar baz')
        self.assertFalse(self.router_worker.scan_for_keywords(
            config,
            msg, (':menu',)))

    def test_create_menu(self):
        config = self.dynamic_config({
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
        self.assertEqual(
            text,
            'Please select a choice\n1) Flappy Bird\n2) Mama'
        )
