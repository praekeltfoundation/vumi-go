from go.vumitools.api_worker import EventDispatcher
from go.vumitools.tests.utils import AppWorkerTestCase
from go.vumitools.opt_out import OptOutStore
from go.vumitools.api import VumiApiEvent, VumiUserApi

from twisted.internet.defer import inlineCallbacks
from twisted.internet.base import DelayedCall
# DelayedCall.debug = True

from vxpolls.manager import PollManager


class EventHandlerTestCase(AppWorkerTestCase):

    application_class = EventDispatcher
    handlers = None

    @inlineCallbacks
    def setUp(self):
        yield super(EventHandlerTestCase, self).setUp()

        app_config = {
            'event_handlers': {},
        }
        for name, handler_class, config in self.handlers:
            app_config['event_handlers'][name] = handler_class
            app_config[name] = config

        self.event_dispatcher = yield self.get_application(app_config)
        self.vumi_api = self.event_dispatcher.vumi_api
        self.account = yield self.vumi_api.account_store.new_user(u'acct')
        self.user_api = VumiUserApi(self.vumi_api, self.account.key)
        self.conversation = yield self.user_api.new_conversation(
            u'survey', u'subject', u'message',
            delivery_tag_pool=u'pool',
            delivery_class=u'sms')

    @inlineCallbacks
    def tearDown(self):
        yield super(EventHandlerTestCase, self).tearDown()
        yield self.event_dispatcher.teardown_application()

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

class USSDOptOutHandlerTestCase(EventHandlerTestCase):

    handlers = [
        ('sisi_ni_amani', 'go.apps.sna.USSDOptOutHandler', {
            'poll_manager_prefix': 'vumigo.'
            })
    ]

    @inlineCallbacks
    def setUp(self):
        yield super(USSDOptOutHandlerTestCase, self).setUp()
        self.contact_store = self.user_api.contact_store
        yield self.contact_store.contacts.enable_search()
        yield self.contact_store.groups.enable_search()
        self.oo_store = OptOutStore(self.vumi_api.manager, self.account.key)
        self.pm = PollManager(self.vumi_api.redis, 'vumigo.')
        self.track_event(self.account.key, self.conversation.key,
            'survey_completed', 'sisi_ni_amani')

    @inlineCallbacks
    def tearDown(self):
        yield super(USSDOptOutHandlerTestCase, self).tearDown()
        self.pm.stop()

    @inlineCallbacks
    def test_opt_in(self):
        msisdn = u'+2345'
        message_id = u'message-id'
        event = self.mkevent('survey_completed', {
            'from_addr': msisdn,
            'message_id': message_id,
            'transport_type': 'ussd',
            }, conv_key=self.conversation.key, account_key=self.account.key)

        yield self.oo_store.new_opt_out('msisdn', msisdn, {
            'message_id': message_id})

        contact = yield self.contact_store.new_contact(msisdn=msisdn)
        contact.extra['opted_out'] = u'1'
        yield contact.save()

        [opt_out] = yield self.oo_store.list_opt_outs()
        self.assertTrue(opt_out)

        yield self.publish_event(event)

        opt_outs = yield self.oo_store.list_opt_outs()
        self.assertEqual(opt_outs, [])

    @inlineCallbacks
    def test_opt_out(self):
        msisdn = u'+2345'
        message_id = u'message-id'
        event = self.mkevent('survey_completed', {
            'from_addr': msisdn,
            'message_id': message_id,
            'transport_type': 'ussd',
            }, conv_key=self.conversation.key, account_key=self.account.key)

        contact = yield self.contact_store.new_contact(msisdn=msisdn)
        contact.extra['opted_out'] = u'2'
        yield contact.save()

        opt_outs = yield self.oo_store.list_opt_outs()
        self.assertEqual(opt_outs, [])

        yield self.publish_event(event)

        [opt_out] = yield self.oo_store.list_opt_outs()
        self.assertTrue(opt_out)
