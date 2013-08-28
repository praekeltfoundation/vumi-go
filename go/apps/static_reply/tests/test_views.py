from go.vumitools.tests.utils import VumiApiCommand
from go.apps.tests.base import DjangoGoApplicationTestCase


class StaticReplyTestCase(DjangoGoApplicationTestCase):
    TEST_CONVERSATION_TYPE = u'static_reply'

    def test_new_conversation(self):
        self.add_app_permission(u'go.apps.static_reply')
        self.assertEqual(len(self.conv_store.list_conversations()), 0)
        response = self.post_new_conversation()
        self.assertEqual(len(self.conv_store.list_conversations()), 1)
        conv = self.get_latest_conversation()
        self.assertRedirects(response, self.get_view_url('edit', conv.key))

    def test_stop(self):
        self.setup_conversation(started=True)
        response = self.client.post(self.get_view_url('stop'), follow=True)
        self.assertRedirects(response, self.get_view_url('show'))
        [msg] = response.context['messages']
        self.assertEqual(str(msg), "Conversation stopped")
        conversation = self.get_wrapped_conv()
        self.assertTrue(conversation.stopping())

    def test_start(self):
        """
        Test the start conversation view
        """
        self.setup_conversation()

        response = self.client.post(self.get_view_url('start'))
        self.assertRedirects(response, self.get_view_url('show'))

        conversation = self.get_wrapped_conv()

        [start_cmd] = self.get_api_commands_sent()
        self.assertEqual(start_cmd, VumiApiCommand.command(
            '%s_application' % (conversation.conversation_type,), 'start',
            user_account_key=conversation.user_account.key,
            conversation_key=conversation.key))

    def test_show_stopped(self):
        """
        Test showing the conversation
        """
        self.setup_conversation()
        response = self.client.get(self.get_view_url('show'))
        conversation = response.context[0].get('conversation')
        self.assertEqual(conversation.name, self.TEST_CONVERSATION_NAME)

    def test_show_running(self):
        """
        Test showing the conversation
        """
        self.setup_conversation(started=True)
        response = self.client.get(self.get_view_url('show'))
        conversation = response.context[0].get('conversation')
        self.assertEqual(conversation.name, self.TEST_CONVERSATION_NAME)

    def test_get_edit_empty_config(self):
        self.setup_conversation()
        response = self.client.get(self.get_view_url('edit'))
        self.assertEqual(response.status_code, 200)

    def test_get_edit_small_config(self):
        self.setup_conversation({'reply_text': 'hello'})
        response = self.client.get(self.get_view_url('edit'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'hello')

    def test_edit_config(self):
        self.setup_conversation()
        conv = self.get_wrapped_conv()
        self.assertEqual(conv.config, {})
        response = self.client.post(self.get_view_url('edit'), {
            'reply_text': 'hello',
        })
        self.assertRedirects(response, self.get_view_url('show'))
        conv = self.get_wrapped_conv()
        self.assertEqual(conv.config, {'reply_text': 'hello'})
