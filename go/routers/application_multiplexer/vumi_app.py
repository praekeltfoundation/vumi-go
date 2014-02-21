# -*- test-case-name: go.routers.application_multiplexer.tests.test_vumi_app -*-
import json

from twisted.internet.defer import inlineCallbacks, returnValue

from vumi import log
from vumi.config import ConfigDict, ConfigList, ConfigInt, ConfigText
from vumi.components.session import SessionManager
from vumi.message import TransportUserMessage

from go.vumitools.app_worker import GoRouterWorker
from go.routers.application_multiplexer.common import mkmenu, clean


class ApplicationMultiplexerConfig(GoRouterWorker.CONFIG_CLASS):

    # Static configuration
    session_expiry = ConfigInt(
        "Maximum amount of time in seconds to keep session data around",
        default=1800, static=True)

    # Dynamic, per-message configuration
    menu_title = ConfigDict(
        "Content for the menu title",
        default={'content': "Please select a choice."})
    entries = ConfigList(
        "A list of application endpoints and associated labels",
        default=[])
    keyword = ConfigText(
        "Keyword to signal a request to return to the application menu",
        default=None)
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
    Router that multiplexes between different endpoints
    on the outbound path.

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
    |  selected      |
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
        d = super(ApplicationMultiplexer, self).setup_router()
        self.handlers = {
            self.STATE_START: self.handle_state_start,
            self.STATE_SELECT: self.handle_state_select,
            self.STATE_SELECTED: self.handle_state_selected,
            self.STATE_BAD_INPUT: self.handle_state_bad_input
        }
        return d

    def session_manager(self, config):
        """
        The implementation of SessionManager does the job of
        appending ':session' to key names.
        """
        return SessionManager.from_redis_config(
            config.redis_manager,
            max_session_length=config.session_expiry
        )

    def target_endpoints(self, config):
        """
        Make sure the currently active endpoint is still valid.
        """
        return set([entry['endpoint'] for entry in config.entries])

    @inlineCallbacks
    def handle_inbound(self, config, msg, conn_name):
        log.msg("Processing inbound message: %s" % (msg,))

        user_id = msg['from_addr']
        session_manager = yield self.session_manager(config)

        session = yield session_manager.load_session(user_id)
        if not session:
            log.msg("Creating session for user %s" % user_id)
            session = {}
            state = self.STATE_START
            yield session_manager.create_session(user_id)
        else:
            log.msg("Loading session for user %s: %s" % (user_id, session,))
            state = session['state']

        try:
            result = yield self.handlers[state](config, session, msg)
            if result is None:
                # Halt session immediately
                # The 'close' message has already been sent back to
                # the user at this point.
                log.msg(("Router configuration change forced session abort "
                         "for user %s" % user_id))
                yield session_manager.clear_session(user_id)
                yield self.publish_error_reply(msg, config)
            else:
                if type(result) is tuple:
                    # Transition to next state AND mutate session data
                    next_state = session['state'] = result[0]
                    session.update(result[1])
                else:
                    # Transition to next state
                    next_state = session['state'] = result
                if state != next_state:
                    log.msg("State transition for user %s: %s => %s" %
                            (user_id, state, next_state))
                yield session_manager.save_session(user_id, session)
        except:
            log.err()
            yield session_manager.clear_session(user_id)
            yield self.publish_error_reply(msg, config)

    @inlineCallbacks
    def handle_state_start(self, config, session, msg):
        """
        When presenting the menu, we also store the list of endpoints
        in the session data. Later, in the SELECT state, we load
        these endpoints and retrieve the candidate endpoint based
        on the user's menu choice.
        """
        reply_msg = msg.reply(self.create_menu(config))
        yield self.publish_outbound(reply_msg)
        endpoints = json.dumps(
            [entry['endpoint'] for entry in config.entries]
        )
        returnValue((self.STATE_SELECT, dict(endpoints=endpoints)))

    @inlineCallbacks
    def handle_state_select(self, config, session, msg):
        endpoint = self.get_endpoint_for_choice(msg, session)
        if endpoint is None:
            reply_msg = msg.reply(config.invalid_input_message)
            yield self.publish_outbound(reply_msg)
            returnValue(self.STATE_BAD_INPUT)
        else:
            if endpoint not in self.target_endpoints(config):
                returnValue(None)
            else:
                forwarded_msg = self.forwarded_message(
                    msg,
                    content=None,
                    session_event=TransportUserMessage.SESSION_NEW
                )
                yield self.publish_inbound(forwarded_msg, endpoint)
                log.msg("Switched to endpoint '%s' for user %s" %
                        (endpoint, msg['from_addr']))
                returnValue((self.STATE_SELECTED,
                             dict(active_endpoint=endpoint)))

    @inlineCallbacks
    def handle_state_selected(self, config, session, msg):
        active_endpoint = session['active_endpoint']
        if active_endpoint not in self.target_endpoints(config):
            returnValue(None)
        elif self.scan_for_keywords(config, msg, (config.keyword,)):
            reply_msg = msg.reply(self.create_menu(config))
            yield self.publish_outbound(reply_msg)

            # Be polite and pass a SESSION_CLOSE to the active endpoint
            forwarded_msg = self.forwarded_message(
                msg,
                content=None,
                session_event=TransportUserMessage.SESSION_CLOSE
            )
            yield self.publish_inbound(forwarded_msg, active_endpoint)
            returnValue((self.STATE_SELECT,
                         dict(active_endpoint=None)))
        else:
            yield self.publish_inbound(msg, active_endpoint)
            returnValue(self.STATE_SELECTED)

    @inlineCallbacks
    def handle_state_bad_input(self, config, session, msg):
        choice = self.get_menu_choice(msg, (1, 1))
        if choice is None:
            reply_msg = msg.reply(config.invalid_input_message)
            yield self.publish_outbound(reply_msg)
            returnValue(self.STATE_BAD_INPUT)
        else:
            result = yield self.handle_state_start(config, session, msg)
            returnValue(result)

    def handle_outbound(self, config, msg, conn_name):
        """
        TODO: Go to SELECT state when session_event=close
        """
        log.msg("Processing outbound message: %s" % (msg,))
        return self.publish_outbound(msg)

    def publish_outbound(self, msg):
        return super(ApplicationMultiplexer, self).publish_outbound(
            msg,
            "default"
        )

    def publish_error_reply(self, msg, config):
        reply_msg = msg.reply(
            config.error_message,
            continue_session=False
        )
        return self.publish_outbound(reply_msg)

    def forwarded_message(self, msg, **kwargs):
        copy = TransportUserMessage(**msg.payload)
        for k, v in kwargs.items():
            copy[k] = v
        return copy

    def scan_for_keywords(self, config, msg, keywords):
        first_word = (clean(msg['content']).split() + [''])[0]
        if first_word in keywords:
            return True
        return False

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
