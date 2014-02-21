import copy
import json

from twisted.internet.defer import inlineCallbacks

from vumi.tests.helpers import VumiTestCase
from go.routers.application_multiplexer.vumi_app import ApplicationMultiplexer
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

    @inlineCallbacks
    def check_state(self, router, state):
        """
        A helper to validate routing behavior.

        The state dict describes the messages which need to be sent, what
        session data to initialize, and what data should be asserted
        when the state handler completes execution.

        Messages are represented by a tuple (content, {field=value, ...})

        This could be made into a generic test helper one day.
        """

        session_manager = yield self.router_worker.session_manager(
            self.router_worker.CONFIG_CLASS(self.router_worker.config)
        )

        # Initialize session data
        for user_id, data in state['session'].items():
            yield session_manager.save_session(user_id, data)

        # Send inbound message via ri
        content, fields = state['ri_inbound']
        msg = yield self.router_helper.ri.make_dispatch_inbound(
            content,
            router=router,
            **fields)

        # If required, send outbound message via ro
        if 'ro_inbound' in state:
            content, fields = state['ro_inbound']
            yield self.router_helper.ro.make_dispatch_reply(
                msg, content, **fields)

        # If required, assert that an outbound message was dispatched to ro
        if 'ro_outbound' in state['expect']:
            content, fields = state['expect']['ro_outbound']
            [msg] = self.router_helper.ro.get_dispatched_inbound()
            self.assertEqual(msg['content'], content,
                             msg="RO Inbound Message: Unexpected content")
            for field, value in fields.items():
                self.assertEqual(
                    msg[field], value,
                    msg=("RO Inbound Message: Unexpected value For field '%s'"
                         % field)
                )

        # Assert that an expected message was dispatched via ri
        [msg] = self.router_helper.ri.get_dispatched_outbound()
        content, fields = state['expect']['ri_outbound']
        self.assertEqual(msg['content'], content,
                         msg="RI Outbound Message: Unexpected content")
        for field, value in fields.items():
            self.assertEqual(
                msg[field], value,
                msg=("RI Outbound Message: Unexpected value For field '%s'"
                     % field)
            )

        # Assert that user session was updated correctly
        for user_id, data in state['expect']['session'].iteritems():
            session = yield session_manager.load_session(user_id)
            if 'created_at' in session:
                del session['created_at']
            self.assertEqual(session, data,
                             msg="Unexpected session data")

    @inlineCallbacks
    def setup_session(self, user_id, data):
        session_manager = yield self.router_worker.session_manager(
            self.router_worker.CONFIG_CLASS(self.router_worker.config)
        )
        # Initialize session data
        yield session_manager.save_session(user_id, data)

    @inlineCallbacks
    def assert_session_state(self, user_id, expected_session):
        session_manager = yield self.router_worker.session_manager(
            self.router_worker.CONFIG_CLASS(self.router_worker.config)
        )
        session = yield session_manager.load_session(user_id)
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
        yield self.check_state(router, {
            'ri_inbound': (':menu', dict(from_addr='2323',
                                         session_event='resume')),
            'session': {
                '2323': {
                    'state': ApplicationMultiplexer.STATE_SELECTED,
                    'active_endpoint': 'flappy-bird',
                    'endpoints': '["flappy-bird"]',
                },
            },
            'expect': {
                'ri_outbound': ('Please select a choice.\n1) Flappy Bird', {}),
                'ro_outbound': (None, dict(session_event='close')),
                'session': {
                    '2323': {
                        'state': ApplicationMultiplexer.STATE_SELECT,
                        'active_endpoint': 'None',
                        # TODO: I should clear session keys which are no longer
                        # relevant in this state
                        'endpoints': '["flappy-bird"]',
                    },
                }
            }
        })

    @inlineCallbacks
    def test_state_select_to_bad_input(self):
        router = yield self.router_helper.create_router(
            started=True,
            config=self.ROUTER_CONFIG
        )
        yield self.check_state(router, {
            'ri_inbound': ('j8', dict(from_addr='2323',
                                      session_event='resume')),
            'session': {
                '2323': {
                    'state': ApplicationMultiplexer.STATE_SELECT,
                    'endpoints': '["flappy-bird"]',
                },
            },
            'expect': {
                'ri_outbound': ('Bad choice.\n1) Try Again', {}),
                'session': {
                    '2323': {
                        'state': ApplicationMultiplexer.STATE_BAD_INPUT,
                        'endpoints': '["flappy-bird"]',
                    },
                }
            }
        })

    @inlineCallbacks
    def test_state_bad_input_to_bad_input(self):
        router = yield self.router_helper.create_router(
            started=True,
            config=self.ROUTER_CONFIG
        )
        yield self.check_state(router, {
            'ri_inbound': ('2', dict(from_addr='2323',
                                     session_event='resume')),
            'session': {
                '2323': {
                    'state': ApplicationMultiplexer.STATE_BAD_INPUT,
                },
            },
            'expect': {
                'ri_outbound': ('Bad choice.\n1) Try Again', {}),
                'session': {
                    '2323': {
                        'state': ApplicationMultiplexer.STATE_BAD_INPUT,
                    },
                }
            }
        })

    @inlineCallbacks
    def test_state_bad_input_to_select(self):
        router = yield self.router_helper.create_router(
            started=True,
            config=self.ROUTER_CONFIG
        )
        yield self.check_state(router, {
            'ri_inbound': ('1', dict(from_addr='2323',
                                     session_event='resume')),
            'session': {
                '2323': {
                    'state': ApplicationMultiplexer.STATE_BAD_INPUT,
                },
            },
            'expect': {
                'ri_outbound': ('Please select a choice.\n1) Flappy Bird', {}),
                'session': {
                    '2323': {
                        'state': ApplicationMultiplexer.STATE_SELECT,
                        'endpoints': '["flappy-bird"]',
                    },
                }
            }
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

        yield self.check_state(router, {
            'ri_inbound': (':menu', dict(from_addr='2323',
                                         session_event='resume')),
            'session': {
                '2323': {
                    'state': ApplicationMultiplexer.STATE_SELECTED,
                    'active_endpoint': 'flappy-bird'
                },
            },
            'expect': {
                'ri_outbound': ('Oops! Sorry!', {}),
                'session': {
                    '2323': {},
                }
            }
        })
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
        yield self.check_state(router, {
            'ri_inbound': ('Up!', dict(from_addr='2323',
                                       session_event='resume')),
            'session': {
                '2323': {
                    'state': ApplicationMultiplexer.STATE_SELECTED,
                    'active_endpoint': 'flappy-bird'
                },
            },
            'expect': {
                'ri_outbound': ('Oops! Sorry!', dict(session_event='close')),
                'session': {
                    '2323': {},
                }
            }
        })

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
