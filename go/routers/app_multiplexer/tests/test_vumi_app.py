import copy

from twisted.internet.defer import inlineCallbacks, returnValue, Deferred

from vumi.tests.helpers import VumiTestCase

from go.routers.app_multiplexer.vumi_app import ApplicationMultiplexer
from go.routers.tests.helpers import RouterWorkerHelper


def raise_error(*args, **kw):
    raise RuntimeError("An anomaly has been detected")


class TestApplicationMultiplexerRouter(VumiTestCase):

    ROUTER_CONFIG = {
        'invalid_input_message': 'Bad choice.\n1) Try Again',
        'error_message': 'Oops! Sorry!',
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

    def dynamic_config_with_router(self, router):
        msg = self.router_helper.make_inbound(None, router=router)
        return self.router_worker.get_config(msg)

    @inlineCallbacks
    def setup_session(self, router, user_id, data):
        config = yield self.dynamic_config_with_router(router)
        session_manager = yield self.router_worker.session_manager(config)
        # Initialize session data
        yield session_manager.save_session(user_id, data)

    @inlineCallbacks
    def assert_session(self, router, user_id, expected_session):
        config = yield self.dynamic_config_with_router(router)
        session_manager = yield self.router_worker.session_manager(config)
        session = yield session_manager.load_session(user_id)
        if 'created_at' in session:
            del session['created_at']
        self.assertEqual(session, expected_session,
                         msg="Unexpected session data")

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
    def test_new_session_display_menu(self):
        """
        Prompt user to choice an application endpoint.
        """
        router = yield self.router_helper.create_router(
            started=True, config=self.ROUTER_CONFIG)
        # msg sent from user
        yield self.router_helper.ri.make_dispatch_inbound(
            None, router=router, from_addr='123')

        # assert that the user received a response
        [msg] = self.router_helper.ri.get_dispatched_outbound()
        self.assertEqual(msg['content'],
                         'Please select a choice.\n1) Flappy Bird')
        # assert that session data updated correctly
        yield self.assert_session(router, '123', {
            'state': ApplicationMultiplexer.STATE_SELECT,
            'endpoints': '["flappy-bird"]',
        })

    @inlineCallbacks
    def test_select_application_endpoint(self):
        """
        Retrieve endpoint choice from user and set currently active
        endpoint.
        """
        router = yield self.router_helper.create_router(
            started=True, config=self.ROUTER_CONFIG)

        yield self.setup_session(router, '123', {
            'state': ApplicationMultiplexer.STATE_SELECT,
            'endpoints': '["flappy-bird"]',
        })

        # msg sent from user
        msg = yield self.router_helper.ri.make_dispatch_inbound(
            '1', router=router, from_addr='123', session_event='resume')

        # assert that message is forwarded to application
        [msg] = self.router_helper.ro.get_dispatched_inbound()
        self.assertEqual(msg['content'], None)
        self.assertEqual(msg['session_event'], 'new')

        # application sends reply
        yield self.router_helper.ro.make_dispatch_reply(msg, 'Flappy Flappy!')

        # assert that the user received a response
        [msg] = self.router_helper.ri.get_dispatched_outbound()
        self.assertEqual(msg['content'], 'Flappy Flappy!')

        yield self.assert_session(router, '123', {
            'state': ApplicationMultiplexer.STATE_SELECTED,
            'active_endpoint': 'flappy-bird',
            'endpoints': '["flappy-bird"]',
        })

    @inlineCallbacks
    def test_session_with_selected_endpoint(self):
        """
        Tests an ongoing USSD session with a previously selected endpoint
        """
        router = yield self.router_helper.create_router(
            started=True, config=self.ROUTER_CONFIG)

        yield self.setup_session(router, '123', {
            'state': ApplicationMultiplexer.STATE_SELECTED,
            'active_endpoint': 'flappy-bird',
            'endpoints': '["flappy-bird"]',
        })

        # msg sent from user
        msg = yield self.router_helper.ri.make_dispatch_inbound(
            'Up!', router=router, from_addr='123', session_event='resume')

        # assert that message is forwarded to application
        [msg] = self.router_helper.ro.get_dispatched_inbound()
        self.assertEqual(msg['content'], 'Up!')
        self.assertEqual(msg['session_event'], 'resume')

        # application sends reply
        yield self.router_helper.ro.make_dispatch_reply(
            msg, 'Game Over!\n1) Try Again!')

        # assert that the user received a response
        [msg] = self.router_helper.ri.get_dispatched_outbound()
        self.assertEqual(msg['content'],
                         'Game Over!\n1) Try Again!')

        yield self.assert_session(router, '123', {
            'state': ApplicationMultiplexer.STATE_SELECTED,
            'active_endpoint': 'flappy-bird',
            'endpoints': '["flappy-bird"]',
        })

    @inlineCallbacks
    def test_bad_input_for_endpoint_choice(self):
        """
        User entered bad input for the endpoint selection menu.
        """
        router = yield self.router_helper.create_router(
            started=True, config=self.ROUTER_CONFIG)

        yield self.setup_session(router, '123', {
            'state': ApplicationMultiplexer.STATE_SELECT,
            'endpoints': '["flappy-bird"]',
        })

        # msg sent from user
        msg = yield self.router_helper.ri.make_dispatch_inbound(
            'foo', router=router, from_addr='123', session_event='resume')

        # assert that the user received a response
        [msg] = self.router_helper.ri.get_dispatched_outbound()
        self.assertEqual(msg['content'],
                         'Bad choice.\n1) Try Again')

        yield self.assert_session(router, '123', {
            'state': ApplicationMultiplexer.STATE_BAD_INPUT,
            'endpoints': '["flappy-bird"]',
        })

    @inlineCallbacks
    def test_state_bad_input_for_bad_input_prompt(self):
        """
        User entered bad input for the prompt telling the user
        that they entered bad input (ha! recursive).
        """
        router = yield self.router_helper.create_router(
            started=True, config=self.ROUTER_CONFIG)

        yield self.setup_session(router, '123', {
            'state': ApplicationMultiplexer.STATE_BAD_INPUT,
            'endpoints': '["flappy-bird"]',
        })

        # msg sent from user
        msg = yield self.router_helper.ri.make_dispatch_inbound(
            'foo', router=router, from_addr='123', session_event='resume')

        # assert that the user received a response
        [msg] = self.router_helper.ri.get_dispatched_outbound()
        self.assertEqual(msg['content'],
                         'Bad choice.\n1) Try Again')

        yield self.assert_session(router, '123', {
            'state': ApplicationMultiplexer.STATE_BAD_INPUT,
            'endpoints': '["flappy-bird"]',
        })

    @inlineCallbacks
    def test_state_good_input_for_bad_input_prompt(self):
        """
        User entered good input for the prompt telling the user
        that they entered bad input.
        """
        router = yield self.router_helper.create_router(
            started=True, config=self.ROUTER_CONFIG)

        yield self.setup_session(router, '123', {
            'state': ApplicationMultiplexer.STATE_BAD_INPUT,
            'endpoints': '["flappy-bird"]',
        })

        # msg sent from user
        msg = yield self.router_helper.ri.make_dispatch_inbound(
            '1', router=router, from_addr='123', session_event='resume')

        # assert that the user received a response
        [msg] = self.router_helper.ri.get_dispatched_outbound()
        self.assertEqual(msg['content'],
                         'Please select a choice.\n1) Flappy Bird')

        yield self.assert_session(router, '123', {
            'state': ApplicationMultiplexer.STATE_SELECT,
            'endpoints': '["flappy-bird"]',
        })

    @inlineCallbacks
    def test_runtime_exception_in_selected_handler(self):
        """
        Verifies that the worker handles an arbitrary runtime error gracefully,
        and sends an appropriate error message back to the user
        """
        router = yield self.router_helper.create_router(
            started=True, config=self.ROUTER_CONFIG)

        # Make worker.target_endpoints raise an exception
        self.patch(self.router_worker,
                   'target_endpoints',
                   raise_error)

        yield self.setup_session(router, '123', {
            'state': ApplicationMultiplexer.STATE_SELECTED,
            'active_endpoint': 'flappy-bird',
            'endpoints': '["flappy-bird"]',
        })

        # msg sent from user
        msg = yield self.router_helper.ri.make_dispatch_inbound(
            'Up!', router=router, from_addr='123', session_event='resume')
        # assert that the user received a response
        [msg] = self.router_helper.ri.get_dispatched_outbound()
        self.assertEqual(msg['content'],
                         'Oops! Sorry!')

        yield self.assert_session(router, '123', {})

        errors = self.flushLoggedErrors(RuntimeError)
        self.assertEqual(len(errors), 1)

    @inlineCallbacks
    def test_session_invalidation_in_state_handler(self):
        """
        Verify that the router gracefully handles a configuration
        update while there is an active user session.

        A session is aborted if there is no longer an attached endpoint
        to which it refers.
        """
        config = copy.deepcopy(self.ROUTER_CONFIG)
        config['entries'][0]['endpoint'] = 'mama'
        router = yield self.router_helper.create_router(
            started=True, config=config)
        yield self.setup_session(router, '123', {
            'state': ApplicationMultiplexer.STATE_SELECTED,
            'active_endpoint': 'flappy-bird',
            'endpoints': '["flappy-bird"]',
        })

        # msg sent from user
        msg = yield self.router_helper.ri.make_dispatch_inbound(
            'Up!', router=router, from_addr='123', session_event='resume')
        # assert that the user received a response
        [msg] = self.router_helper.ri.get_dispatched_outbound()
        self.assertEqual(msg['content'],
                         'Oops! Sorry!')
        yield self.assert_session(router, '123', {})

    @inlineCallbacks
    def test_state_selected_receive_close_inbound(self):
        """
        User sends 'close' msg to the active endpoint via the router.
        Verify that the message is forwarded and that the session for
        the user is cleared.
        """
        router = yield self.router_helper.create_router(
            started=True, config=self.ROUTER_CONFIG)

        yield self.setup_session(router, '123', {
            'state': ApplicationMultiplexer.STATE_SELECTED,
            'active_endpoint': 'flappy-bird',
            'endpoints': '["flappy-bird"]',
        })

        # msg sent from user
        msg = yield self.router_helper.ri.make_dispatch_inbound(
            None, router=router, from_addr='123', session_event='close')

        # assert app received forwarded 'close' message
        [msg] = self.router_helper.ro.get_dispatched_inbound()
        self.assertEqual(msg['content'], None)
        self.assertEqual(msg['session_event'], 'close')

        # assert that no response sent to user
        msgs = self.router_helper.ri.get_dispatched_outbound()
        self.assertEqual(msgs, [])

        # assert that session cleared
        yield self.assert_session(router, '123', {})

    @inlineCallbacks
    def test_receive_close_inbound(self):
        """
        Same as the above test, but only for the case when
        an active endpoint has not yet been selected.
        """
        router = yield self.router_helper.create_router(
            started=True, config=self.ROUTER_CONFIG)

        yield self.setup_session(router, '123', {
            'state': ApplicationMultiplexer.STATE_SELECT,
            'endpoints': '["flappy-bird"]'
        })

        # msg sent from user
        msg = yield self.router_helper.ri.make_dispatch_inbound(
            None, router=router, from_addr='123', session_event='close')

        # assert that no app received a forwarded 'close' message
        msgs = self.router_helper.ro.get_dispatched_inbound()
        self.assertEqual(msgs, [])
        self.assertEqual(msg['session_event'], 'close')

        # assert that no response sent to user
        msgs = self.router_helper.ri.get_dispatched_outbound()
        self.assertEqual(msgs, [])

        # assert that session cleared
        yield self.assert_session(router, '123', {})

    @inlineCallbacks
    def test_receive_close_outbound(self):
        """
        Application sends a 'close' message to the user via
        the router. Verify that the message is forwarded correctly,
        and that the session is terminated.
        """
        router = yield self.router_helper.create_router(
            started=True, config=self.ROUTER_CONFIG)

        yield self.setup_session(router, '123', {
            'state': ApplicationMultiplexer.STATE_SELECTED,
            'active_endpoint': 'flappy-bird',
            'endpoints': '["flappy-bird"]',
        })

        # msg sent from user
        msg = yield self.router_helper.ri.make_dispatch_inbound(
            "3", router=router, from_addr='123', session_event='resume')

        # application quits session
        yield self.router_helper.ro.make_dispatch_reply(
            msg, 'Game Over!', session_event='close')

        # assert that user receives the forwarded 'close' message
        [msg] = self.router_helper.ri.get_dispatched_outbound()
        self.assertEqual(msg['content'], 'Game Over!')
        self.assertEqual(msg['session_event'], 'close')

        # assert that session cleared
        yield self.assert_session(router, '123', {})

    def test_get_menu_choice(self):
        """
        Verify that we parse user input correctly for menu prompts.
        """
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

    @inlineCallbacks
    def test_create_menu(self):
        """
        Create a menu prompt to choose between linked endpoints
        """
        router = yield self.router_helper.create_router(
            started=True, config={
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
        config = yield self.dynamic_config_with_router(router)
        text = self.router_worker.create_menu(config)
        self.assertEqual(
            text, 'Please select a choice\n1) Flappy Bird\n2) Mama')

    @inlineCallbacks
    def test_new_session_stores_valid_session_data(self):
        """
        Starting a new session sets all relevant session fields.
        """
        router = yield self.router_helper.create_router(
            started=True, config=self.ROUTER_CONFIG)

        worker = self.router_worker
        orig_handler = worker.handlers[worker.STATE_START]
        pause_handler_d = Deferred()
        unpause_handler_d = Deferred()

        @inlineCallbacks
        def pause_handler(*args, **kw):
            pause_handler_d.callback(None)
            yield unpause_handler_d
            resp = yield orig_handler(*args, **kw)
            returnValue(resp)

        worker.handlers[worker.STATE_START] = pause_handler

        # msg sent from user
        self.router_helper.ri.make_dispatch_inbound(
            None, router=router, from_addr='123')
        yield pause_handler_d

        # assert that the created session data is correct, then unpause
        yield self.assert_session(router, '123', {
            'state': ApplicationMultiplexer.STATE_START,
        })
        unpause_handler_d.callback(None)

        # assert that the user received a response
        [msg] = self.router_helper.ri.get_dispatched_outbound()
        self.assertEqual(msg['content'],
                         'Please select a choice.\n1) Flappy Bird')
        # assert that session data updated correctly
        yield self.assert_session(router, '123', {
            'state': ApplicationMultiplexer.STATE_SELECT,
            'endpoints': '["flappy-bird"]',
        })
