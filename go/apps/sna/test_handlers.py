
from twisted.internet.defer import inlineCallbacks

from vumi.tests.helpers import VumiTestCase

from vxpolls.manager import PollManager

from go.apps.sna import USSDOptOutHandler, USSDMenuCompletionHandler
from go.vumitools.opt_out import OptOutStore
from go.vumitools.tests.helpers import EventHandlerHelper


class TestUSSDOptOutHandler(VumiTestCase):

    @inlineCallbacks
    def setUp(self):
        self.eh_helper = self.add_helper(EventHandlerHelper())
        yield self.eh_helper.setup_event_dispatcher(
            'sisi_ni_amani', USSDOptOutHandler, {
                'poll_manager_prefix': 'vumigo.',
            })

        vumi_api = self.eh_helper.vumi_helper.get_vumi_api()
        user_helper = yield self.eh_helper.vumi_helper.get_or_create_user()
        self.contact_store = user_helper.user_api.contact_store
        self.oo_store = OptOutStore(vumi_api.manager, user_helper.account_key)

        self.pm = PollManager(vumi_api.redis, 'vumigo.')
        self.add_cleanup(self.pm.stop)

        self.eh_helper.track_event('survey_completed', 'sisi_ni_amani')

    @inlineCallbacks
    def test_opt_in(self):
        msisdn = u'+2345'
        message_id = u'message-id'
        event = self.eh_helper.make_event('survey_completed', {
            'from_addr': msisdn,
            'message_id': message_id,
            'transport_type': 'ussd',
        })

        yield self.oo_store.new_opt_out('msisdn', msisdn, {
            'message_id': message_id})

        contact = yield self.contact_store.new_contact(msisdn=msisdn)
        contact.extra['opted_out'] = u'1'
        yield contact.save()

        [opt_out] = yield self.oo_store.list_opt_outs()
        self.assertTrue(opt_out)

        yield self.eh_helper.dispatch_event(event)

        opt_outs = yield self.oo_store.list_opt_outs()
        self.assertEqual(opt_outs, [])

    @inlineCallbacks
    def test_opt_out(self):
        msisdn = u'+2345'
        message_id = u'message-id'
        event = self.eh_helper.make_event('survey_completed', {
            'from_addr': msisdn,
            'message_id': message_id,
            'transport_type': 'ussd',
        })

        contact = yield self.contact_store.new_contact(msisdn=msisdn)
        contact.extra['opted_out'] = u'2'
        yield contact.save()

        opt_outs = yield self.oo_store.list_opt_outs()
        self.assertEqual(opt_outs, [])

        yield self.eh_helper.dispatch_event(event)

        [opt_out] = yield self.oo_store.list_opt_outs()
        self.assertTrue(opt_out)

    @inlineCallbacks
    def test_opt_out_for_empty_outed_out_value(self):
        msisdn = u'+2345'
        message_id = u'message-id'
        event = self.eh_helper.make_event('survey_completed', {
            'from_addr': msisdn,
            'message_id': message_id,
            'transport_type': 'ussd',
        })

        contact = yield self.contact_store.new_contact(msisdn=msisdn)
        contact.extra['opted_out'] = u''
        yield contact.save()

        opt_outs = yield self.oo_store.list_opt_outs()
        self.assertEqual(opt_outs, [])

        yield self.eh_helper.dispatch_event(event)

        opt_outs = yield self.oo_store.list_opt_outs()
        self.assertEqual(opt_outs, [])


class TestUSSDMenuCompletionHandler(VumiTestCase):

    @inlineCallbacks
    def setUp(self):
        self.eh_helper = self.add_helper(EventHandlerHelper())
        yield self.eh_helper.setup_event_dispatcher(
            'sisi_ni_amani', USSDMenuCompletionHandler, {})

        user_helper = yield self.eh_helper.vumi_helper.get_or_create_user()
        self.contact_store = user_helper.user_api.contact_store
        self.contact = yield self.contact_store.new_contact(
            msisdn=u'+27761234567')

        self.eh_helper.track_event(
            'survey_completed', 'sisi_ni_amani', handler_config={
                'sms_copy': {
                    'english': 'english sms',
                    'swahili': 'swahili sms',
                },
                'conversation_key': self.eh_helper.conversation.key,
            })

    def send_event(self, msisdn):
        event = self.eh_helper.make_event('survey_completed', {
            'from_addr': msisdn,
            'message_id': 'message-id',
            'transport_type': 'ussd',
        })
        return self.eh_helper.dispatch_event(event)

    @inlineCallbacks
    def test_handle_event_default(self):
        yield self.send_event(self.contact.msisdn)
        [command] = self.eh_helper.get_dispatched_commands()

        self.assertEqual(command['command'], 'send_message')
        self.assertEqual(command['kwargs'], {
            'command_data': {
                'batch_id': self.eh_helper.conversation.batch.key,
                'content': 'english sms',
                'to_addr': self.contact.msisdn,
                'msg_options': {},
            }
        })

    @inlineCallbacks
    def test_handle_event_english(self):
        self.contact.extra['language'] = u'1'
        yield self.contact.save()
        yield self.send_event(self.contact.msisdn)
        [command] = self.eh_helper.get_dispatched_commands()

        self.assertEqual(command['args'],
                         [self.eh_helper.conversation.user_account.key,
                          self.eh_helper.conversation.key])
        data = command['kwargs']['command_data']
        self.assertEqual(data['content'], 'english sms')

    @inlineCallbacks
    def test_handle_event_swahili(self):
        self.contact.extra['language'] = u'2'
        yield self.contact.save()
        yield self.send_event(self.contact.msisdn)
        [command] = self.eh_helper.get_dispatched_commands()

        self.assertEqual(command['args'],
                         [self.eh_helper.conversation.user_account.key,
                          self.eh_helper.conversation.key])
        data = command['kwargs']['command_data']
        self.assertEqual(data['content'], 'swahili sms')
