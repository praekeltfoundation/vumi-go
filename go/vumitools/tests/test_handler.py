from go.vumitools.api_worker import EventDispatcher
from go.vumitools.tests.utils import AppWorkerTestCase
from go.vumitools.api import VumiApiEvent

from twisted.internet.defer import inlineCallbacks


class EventHandlerTestCase(AppWorkerTestCase):

    application_class = EventDispatcher
    handlers = None

    @inlineCallbacks
    def setUp(self):
        yield super(EventHandlerTestCase, self).setUp()
        app_config = self.mk_config({
            'event_handlers': {},
        })
        for name, handler_class, config in self.handlers:
            app_config['event_handlers'][name] = handler_class
            app_config[name] = config

        self.event_dispatcher = yield self.get_application(app_config)
        self.vumi_api = self.event_dispatcher.vumi_api
        self.account = yield self.mk_user(self.vumi_api, u'acct')
        self.user_api = self.vumi_api.get_user_api(self.account.key)
        yield self.setup_tagpools()
        self.conversation = yield self.create_conversation(
            conversation_type=u'survey', subject=u'subject',
            message=u'message', delivery_tag_pool=u'pool')

    def publish_event(self, event):
        return self.dispatch(event, rkey='vumi.event')

    def mkevent(self, event_type, content, conv_key=None,
                account_key=None):
        return VumiApiEvent.event(
            account_key or self.account.key,
            conv_key or self.conversation.key,
            event_type, content)

    def track_event(self, account_key, conversation_key, event_type,
                        handler_name, handler_config={}):
        handler_configs = self.event_dispatcher.account_handler_configs
        account_handlers = handler_configs.setdefault(account_key, [])

        account_handlers.append([
            [conversation_key, event_type], [
                [handler_name, handler_config]
            ]
        ])
