# -*- test-case-name: go.routers.app_multiplexer.tests.test_vumi_app -*-
import json

from twisted.internet.defer import inlineCallbacks, returnValue, succeed

from vumi import log
from vumi.config import ConfigDict, ConfigList, ConfigInt, ConfigText
from vumi.components.session import SessionManager
from vumi.message import TransportUserMessage

from go.vumitools.app_worker import GoRouterWorker
from go.routers.app_multiplexer.common import mkmenu, clean


class ApplicationMultiplexerConfig(GoRouterWorker.CONFIG_CLASS):

    # Static configuration
    session_expiry = ConfigInt(
        "Maximum amount of time in seconds to keep session data around",
        default=300, static=True)

    # Dynamic, per-message configuration
    menu_title = ConfigDict(
        "Content for the menu title",
        default={'content': "Please select a choice."})
    entries = ConfigList(
        "A list of application endpoints and associated labels",
        default=[])
    invalid_input_message = ConfigText(
        "Prompt to display when warning about an invalid choice",
        default=("That is an incorrect choice. Please enter the number "
                 "of the menu item you wish to choose.\n\n 1) Try Again"))
    error_message = ConfigText(
        ("Prompt to display when a configuration change invalidates "
         "an active session."),
        default=("Oops! We experienced a temporary error. "
                 "Please try and dial the line again."))


class ApplicationMultiplexer(GoRouterWorker):
    """
    Router that multiplexes between different endpoints on the outbound path.

    State Diagram (for fun):

    +----------------+
    |                |
    |  start         |
    |                |
    +----+-----------+
         |
         |
    +----*-----------+    +----------------+
    |                *----+                |
    |  select        |    |  bad_input     |
    |                +----*                |
    +----+----*------+    +----------------+
         |    |
         |    |
    +----*----+------+
    |                |
    |  selected      +
    |                |
    +----------------+
    """

    CONFIG_CLASS = ApplicationMultiplexerConfig

    worker_name = 'application_multiplexer'

    STATE_START = "start"
    STATE_SELECT = "select"
    STATE_SELECTED = "selected"
    STATE_BAD_INPUT = "bad_input"

    def setup_router(self):
        self.handlers = {
            self.STATE_START: self.handle_state_start,
            self.STATE_SELECT: self.handle_state_select,
            self.STATE_SELECTED: self.handle_state_selected,
            self.STATE_BAD_INPUT: self.handle_state_bad_input,
        }
        return super(ApplicationMultiplexer, self).setup_router()

    def session_manager(self, config):
        key_prefix = ':'.join((self.worker_name, config.router.key))
        redis = self.redis.sub_manager(key_prefix)
        return SessionManager(redis, max_session_length=config.session_expiry)

    def target_endpoints(self, config):
        """
        Make sure the currently active endpoint is still valid.
        """
        return set([entry['endpoint'] for entry in config.entries])

    @inlineCallbacks
    def handle_inbound(self, config, msg, conn_name):
        """
        Main delegation point for handling inbound messages and
        managing the state machine.
        """

        log.msg("Processing inbound message: %s" % (msg,))

        user_id = msg['from_addr']
        session_manager = yield self.session_manager(config)
        session = yield session_manager.load_session(user_id)
        session_event = msg['session_event']
        if not session or session_event == TransportUserMessage.SESSION_NEW:
            log.msg("Creating session for user %s" % user_id)
            session = {}
            state = self.STATE_START
            yield session_manager.create_session(user_id, state=state)
        elif session_event == TransportUserMessage.SESSION_CLOSE:
            yield self.handle_session_close(config, session, msg)
            return
        else:
            log.msg("Loading session for user %s: %s" % (user_id, session,))
            state = session['state']

        try:
            handler = self.handlers[state]
            next_state, session_update, inbound, outbound = yield handler(
                config, session, msg)
            if next_state is None:
                # Session terminated (right now, just in the case of a
                # administrator-initiated configuration change
                yield session_manager.clear_session(user_id)
            else:
                session['state'] = next_state
                session.update(session_update)
                if state != next_state:
                    log.msg("State transition for user %s: %s => %s" %
                            (user_id, state, next_state))
                yield session_manager.save_session(user_id, session)
            for msg, endpoint in inbound:
                yield self.publish_inbound(msg, endpoint)
            for msg in outbound:
                yield self.publish_outbound(msg)
        except:
            log.err()
            yield session_manager.clear_session(user_id)
            yield self.publish_outbound(self.make_error_reply(msg, config))

    def handle_state_start(self, config, session, msg):
        """
        When presenting the menu, we also store the list of endpoints
        in the session data. Later, in the SELECT state, we load
        these endpoints and retrieve the candidate endpoint based
        on the user's menu choice.
        """
        reply_msg = msg.reply(self.create_menu(config))
        endpoints = json.dumps(
            [entry['endpoint'] for entry in config.entries]
        )
        return succeed((
            self.STATE_SELECT, {'endpoints': endpoints}, [], [reply_msg]))

    def handle_state_select(self, config, session, msg):
        endpoint = self.get_endpoint_for_choice(msg, session)
        if endpoint is None:
            reply_msg = msg.reply(config.invalid_input_message)
            return succeed((self.STATE_BAD_INPUT, {}, [], [reply_msg]))

        if endpoint not in self.target_endpoints(config):
            log.msg(("Router configuration change forced session "
                     "termination for user %s" % msg['from_addr']))
            error_reply_msg = self.make_error_reply(msg, config)
            return succeed((None, {}, [], [error_reply_msg]))

        forwarded_msg = self.forwarded_message(
            msg, content=None,
            session_event=TransportUserMessage.SESSION_NEW)
        log.msg("Switched to endpoint '%s' for user %s" %
                (endpoint, msg['from_addr']))
        return succeed((self.STATE_SELECTED, {'active_endpoint': endpoint},
                        [(forwarded_msg, endpoint)], []))

    def handle_state_selected(self, config, session, msg):
        active_endpoint = session['active_endpoint']
        if active_endpoint not in self.target_endpoints(config):
            log.msg(("Router configuration change forced session "
                     "termination for user %s" % msg['from_addr']))
            error_reply_msg = self.make_error_reply(msg, config)
            return succeed((None, {}, [], [error_reply_msg]))
        else:
            return succeed(
                (self.STATE_SELECTED, {}, [(msg, active_endpoint)], []))

    def handle_state_bad_input(self, config, session, msg):
        choice = self.get_menu_choice(msg, (1, 1))
        if choice is None:
            reply_msg = msg.reply(config.invalid_input_message)
            return succeed((self.STATE_BAD_INPUT, {}, [], [reply_msg]))
        else:
            return self.handle_state_start(config, session, msg)

    @inlineCallbacks
    def handle_outbound(self, config, msg, conn_name):
        log.msg("Processing outbound message: %s" % (msg,))
        user_id = msg['to_addr']
        session_event = msg['session_event']
        session_manager = yield self.session_manager(config)
        session = yield session_manager.load_session(user_id)
        if session and (session_event == TransportUserMessage.SESSION_CLOSE):
            yield session_manager.clear_session(user_id)
        yield self.publish_outbound(msg)

    @inlineCallbacks
    def handle_session_close(self, config, session, msg):
        user_id = msg['from_addr']
        if (session.get('state', None) == self.STATE_SELECTED and
                session['active_endpoint'] in self.target_endpoints(config)):
            yield self.publish_inbound(msg, session['active_endpoint'])
        session_manager = yield self.session_manager(config)
        yield session_manager.clear_session(user_id)

    def publish_outbound(self, msg):
        return super(ApplicationMultiplexer, self).publish_outbound(
            msg, "default")

    def make_error_reply(self, msg, config):
        return msg.reply(config.error_message, continue_session=False)

    def forwarded_message(self, msg, **kwargs):
        copy = TransportUserMessage(**msg.payload)
        for k, v in kwargs.items():
            copy[k] = v
        return copy

    def get_endpoint_for_choice(self, msg, session):
        """
        Retrieves the candidate endpoint based on the user's numeric choice
        """
        endpoints = json.loads(session['endpoints'])
        index = self.get_menu_choice(msg, (1, len(endpoints)))
        if index is None:
            return None
        return endpoints[index - 1]

    def get_menu_choice(self, msg, valid_range):
        """
        Parse user input for selecting a numeric menu choice
        """
        try:
            value = int(clean(msg['content']))
        except ValueError:
            return None
        else:
            if value not in range(valid_range[0], valid_range[1] + 1):
                return None
            return value

    def create_menu(self, config):
        labels = [entry['label'] for entry in config.entries]
        return (config.menu_title['content'] + "\n" + mkmenu(labels))
