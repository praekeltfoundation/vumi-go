from go.vumitools.opt_out import OptOutStore
from go.vumitools.tests.test_handler import EventHandlerTestCase

from twisted.internet.defer import inlineCallbacks

from vxpolls.manager import PollManager


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

    @inlineCallbacks
    def test_opt_out_for_empty_outed_out_value(self):
        msisdn = u'+2345'
        message_id = u'message-id'
        event = self.mkevent('survey_completed', {
            'from_addr': msisdn,
            'message_id': message_id,
            'transport_type': 'ussd',
            }, conv_key=self.conversation.key, account_key=self.account.key)

        contact = yield self.contact_store.new_contact(msisdn=msisdn)
        contact.extra['opted_out'] = u''
        yield contact.save()

        opt_outs = yield self.oo_store.list_opt_outs()
        self.assertEqual(opt_outs, [])

        yield self.publish_event(event)

        opt_outs = yield self.oo_store.list_opt_outs()
        self.assertEqual(opt_outs, [])


class USSDMenuCompletionHandlerTestCase(EventHandlerTestCase):

    handlers = [
        ('sisi_ni_amani', 'go.apps.sna.USSDMenuCompletionHandler', {}),
    ]

    @inlineCallbacks
    def setUp(self):
        yield super(USSDMenuCompletionHandlerTestCase, self).setUp()
        yield self.conversation.start()
        [self.tag] = yield self.conversation.get_tags()
        self.msg_options = yield self.conversation.make_message_options(
            self.tag)
        self.track_event(self.account.key, self.conversation.key,
            'survey_completed', 'sisi_ni_amani', handler_config={
                'sms_content': 'foo',
                'conversation_key': self.conversation.key,
            })

    @inlineCallbacks
    def test_handle_event(self):
        event = self.mkevent('survey_completed', {
            'from_addr': 'msisdn',
            'message_id': 'message-id',
            'transport_type': 'ussd',
            }, conv_key=self.conversation.key, account_key=self.account.key)
        yield self.publish_event(event)
        [start_cmd, send_msg_command] = self.get_dispatcher_commands()

        self.assertEqual(start_cmd['command'], 'start')
        self.assertEqual(start_cmd['kwargs'], {
            'batch_id': (yield self.conversation.get_latest_batch_key()),
            'conversation_key': self.conversation.key,
            'conversation_type': self.conversation.conversation_type,
            'is_client_initiated': (
                yield self.conversation.is_client_initiated()),
            'msg_options': self.msg_options,
        })

        self.assertEqual(send_msg_command['command'], 'send_message')
        self.assertEqual(send_msg_command['kwargs'], {
            'command_data': {
                'batch_id': (yield self.conversation.get_latest_batch_key()),
                'content': 'foo',
                'to_addr': 'msisdn',
                'msg_options': self.msg_options,
            }
        })
