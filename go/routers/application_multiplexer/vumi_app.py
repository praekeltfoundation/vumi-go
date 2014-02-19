# Local Variables:
# test-case-name: go.routers.application_multiplexer.tests.test_vumi_app
# coding: utf-8
# End:

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

    session_data_version = ConfigInt(
        "Just in case we need to modify the schema of session storage",
        default=1, static=True)

    # Dynamic, per-message configuration
    menu_title = ConfigDict(
        "Content for the menu title",
        default={'content': "Please select a choice."})
    entries = ConfigList(
        "A list of application endpoints and associated labels",
        default=[])
    keyword = ConfigText(
        "Keyword to signal a request to return to the application menu",
        default=':menu')
    invalid_input_message = ConfigText(
        "Prompt to display when warning about an invalid choice",
        default=("That is an incorrect choice. Please enter the number "
                 "next to the menu item you wish to choose.\n\n 1) Try Again"))
    error_message = ConfigText(
        ("Prompt to display when a configuration change invalidates "
         "an active session."),
        default=("Oops! We experienced a temporary error. "
                 "Please dial the line again."))


class ApplicationMultiplexer(GoRouterWorker):
    """
    Router that splits inbound messages based on keywords.
    """
    CONFIG_CLASS = ApplicationMultiplexerConfig

    worker_name = 'application_multiplexer'

    STATE_START = "start"
    STATE_SELECT = "select"
    STATE_SELECTED = "selected"
    STATE_BAD_INPUT = "bad_input"

    HANDLERS = {
        STATE_START: 'handle_state_start',
        STATE_SELECT: 'handle_state_select',
        STATE_SELECTED: 'handle_state_selected',
        STATE_BAD_INPUT: 'handle_state_bad_input'
    }

    def setup_router(self):
        return super(ApplicationMultiplexer, self).setup_router()

    def teardown_router(self):
        return super(ApplicationMultiplexer, self).teardown_router()

    def session_manager(self, config):
        """
        The implementation of SessionManager does the job of
        appending ':session' to key names.
        """
        return SessionManager.from_redis_config(
            config.redis_manager,
            max_session_length=config.session_expiry
        )

    def valid_target_endpoint(self, config, active_endpoint):
        """
        Make sure the currently active endpoint is still valid.
        """
        endpoints = set([entry['endpoint'] for entry in config.entries])
        if active_endpoint not in endpoints:
            return False
        return True

    @inlineCallbacks
    def handle_inbound(self, config, msg, conn_name):
        log.msg("Processing inbound message: %s" % (msg,))

        user_id = msg['from_addr']
        session_manager = self.session_manager(config)

        session = yield session_manager.load_session(user_id)
        if session is None:
            log.msg("Creating session for user %s" % user_id)
            state = self.STATE_START
            session = {
                'version': config.session_data_version,
            }
            yield session_manager.create_session(user_id, **session)
        else:
            log.msg("Loading session for user %s: %s" % (session,))
            state = session['state']

        try:
            handler = getattr(self, self.HANDLERS[state])
            result = yield handler(config, session, msg)
            if type(result) is tuple:
                next_state = session['state'] = result[0]
                session.update(result[1])
            else:
                next_state = session['state'] = result
            if state != next_state:
                log.msg("State transition for user %s: %s => %s"
                        (user_id, state, next_state))
        except:
            log.err()
            yield session_manager.clear_session(user_id)
            reply_msg = msg.reply(
                config.error_message,
                continue_session=False
            )
            self.publish_outbound(reply_msg, 'default')
        else:
            yield session_manager.save_session(user_id, **session)

    @inlineCallbacks
    def handle_state_start(self, config, session, msg):
        reply_msg = msg.reply(self.create_menu(config))
        yield self.publish_outbound(reply_msg, 'default')
        returnValue(self.STATE_CHOOSE)

    @inlineCallbacks
    def handle_state_select(self, config, session, msg):
        """
        NOTE: There is an edge case in which the user input no longer
        matches an entry in the current config. The impact depends
        on the number of users and how often the router config is modified.

        One solution would be to compare hashes of the menu configs as
        they existed at the START and SELECT states. If there is a mismatch,
        invalidate the current session.
        """
        choice = self.get_menu_choice(msg, (1, len(config.entries)))
        if choice is None:
            reply_msg = msg.reply(config.invalid_input_message)
            yield self.publish_outbound(reply_msg, 'default')
            returnValue(self.STATE_BAD_CHOICE)
        else:
            endpoint = config.entries[choice - 1]['endpoint']
            forwarded_msg = TransportUserMessage(**msg.payload)
            forwarded_msg['content'] = None
            forwarded_msg['session_event'] = TransportUserMessage.SESSION_START
            yield self.publish_inbound(forwarded_msg, endpoint)
            log.msg("Switched to endpoint '%s' for user %s" %
                    (endpoint, msg['from_addr']))
            returnValue((self.STATE_SELECTED, dict(active_endpoint=endpoint)))

    @inlineCallbacks
    def handle_state_selected(self, config, session, msg):
        active_endpoint = session['active_endpoint']
        if not self.valid_target_endpoint(config, active_endpoint):
            reply_msg = msg.reply(
                config.error_message,
                continue_session=False
            )
            yield self.publish_outbound(reply_msg, 'default')
            returnValue(None)
        elif self.scan_for_keywords(config, msg, (config.keyword,)):
            reply_msg = msg.reply(self.create_menu(config))
            yield self.publish_outbound(reply_msg, 'default')

            # Be polite and pass a SESSION_CLOSE to the active endpoint
            close_msg = TransportUserMessage(**msg.payload)
            close_msg['content'] = None
            close_msg['session_event'] = TransportUserMessage.SESSION_CLOSE
            yield self.publish_inbound(close_msg, active_endpoint)
            returnValue((self.STATE_SELECT, dict(active_endpoint=None)))
        else:
            yield self.publish_inbound(msg, active_endpoint)
            returnValue(self.STATE_SELECTED)

    @inlineCallbacks
    def handle_state_bad_choice(self, config, session, msg):
        choice = self.get_menu_choice(msg, (1, 1))
        if choice is None:
            reply_msg = msg.reply(config.invalid_input_message)
            yield self.publish_outbound(reply_msg, 'default')
            returnValue(self.STATE_BAD_CHOICE)
        else:
            reply_msg = msg.reply(self.create_menu(config))
            yield self.publish_outbound(reply_msg, 'default')
            returnValue(self.STATE_SELECT)

    def handle_outbound(self, config, msg, conn_name):
        """
        TODO: Go to SELECT state when session_event=close
        """
        log.msg("Processing outbound message: %s" % (msg,))
        return self.publish_outbound(msg, 'default')

    def scan_for_keywords(self, config, msg, keywords):
        first_word = (clean(msg['content']).split() + [''])[0]
        if first_word in keywords:
            return True
        return False

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
