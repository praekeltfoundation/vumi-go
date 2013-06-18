from django.test.client import Client
from django.core.urlresolvers import reverse

from go.vumitools.tests.utils import VumiApiCommand
from go.apps.tests.base import DjangoGoApplicationTestCase
from go.base.utils import get_conversation_view_definition
from go.conversation.conversation_views import ConversationViewFinder


class SubscriptionTestCase(DjangoGoApplicationTestCase):
    TEST_CONVERSATION_TYPE = u'subscription'

    def setUp(self):
        super(SubscriptionTestCase, self).setUp()
        self.setup_riak_fixtures()
        self.client = Client()
        self.client.login(username='username', password='password')

    def get_view_url(self, view, conv_key=None):
        if conv_key is None:
            conv_key = self.conv_key
        view_def = get_conversation_view_definition(
            self.TEST_CONVERSATION_TYPE)
        finder = ConversationViewFinder(view_def)
        return finder.get_view_url(view, conversation_key=conv_key)

    def get_new_view_url(self):
        return reverse('conversations:new_conversation', kwargs={
            'conversation_type': self.TEST_CONVERSATION_TYPE})

    def get_wrapped_conv(self):
        conv = self.conv_store.get_conversation_by_key(self.conv_key)
        return self.user_api.wrap_conversation(conv)

    def run_new_conversation(self, selected_option, pool, tag):
        # render the form
        self.assertEqual(len(self.conv_store.list_conversations()), 1)
        response = self.client.get(self.get_new_view_url())
        self.assertEqual(response.status_code, 200)
        # post the form
        response = self.client.post(self.get_new_view_url(), {
            'subject': 'the subject',
            'message': 'the message',
            'delivery_class': 'sms',
            'delivery_tag_pool': selected_option,
        })
        self.assertEqual(len(self.conv_store.list_conversations()), 2)
        conversation = self.get_latest_conversation()
        self.assertEqual(conversation.delivery_class, 'sms')
        self.assertEqual(conversation.delivery_tag_pool, pool)
        self.assertEqual(conversation.delivery_tag, tag)
        self.assertRedirects(
            response, self.get_view_url('edit', conversation.key))

    def test_new_conversation(self):
        """test the creation of a new conversation"""
        self.run_new_conversation('longcode:', 'longcode', None)

    def test_new_conversation_with_user_selected_tags(self):
        tp_meta = self.api.tpm.get_metadata('longcode')
        tp_meta['user_selects_tag'] = True
        self.api.tpm.set_metadata('longcode', tp_meta)
        self.run_new_conversation('longcode:default10001', 'longcode',
                                  'default10001')

    def test_end(self):
        """
        Test ending the conversation
        """
        conversation = self.get_wrapped_conv()
        self.assertFalse(conversation.ended())
        response = self.client.post(self.get_view_url('end'), follow=True)
        self.assertRedirects(response, self.get_view_url('show'))
        [msg] = response.context['messages']
        self.assertEqual(str(msg), "Conversation ended")
        conversation = self.get_wrapped_conv()
        self.assertTrue(conversation.ended())

    def test_start(self):
        """
        Test the start conversation view
        """
        conversation = self.get_wrapped_conv()

        response = self.client.post(self.get_view_url('start'))
        self.assertRedirects(response, self.get_view_url('show'))

        conversation = self.get_wrapped_conv()
        [batch] = conversation.get_batches()
        [tag] = list(batch.tags)
        [contact] = self.get_contacts_for_conversation(conversation)

        [start_cmd] = self.get_api_commands_sent()
        self.assertEqual(start_cmd, VumiApiCommand.command(
                '%s_application' % (conversation.conversation_type,), 'start',
                user_account_key=conversation.user_account.key,
                conversation_key=conversation.key))

    def test_send_fails(self):
        """
        Test failure to send messages
        """
        self.acquire_all_longcode_tags()
        response = self.client.post(self.get_view_url('start'), follow=True)
        self.assertRedirects(response, self.get_view_url('start'))
        [] = self.get_api_commands_sent()
        [msg] = response.context['messages']
        self.assertEqual(str(msg), "No spare messaging tags.")

    def test_show(self):
        """
        Test showing the conversation
        """
        response = self.client.get(self.get_view_url('show'))
        conversation = response.context[0].get('conversation')
        self.assertEqual(conversation.name, self.TEST_CONVERSATION_NAME)
