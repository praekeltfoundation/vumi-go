from go.vumitools.tests.utils import VumiApiCommand
from go.apps.tests.base import DjangoGoApplicationTestCase


class SequentialSendTestCase(DjangoGoApplicationTestCase):
    TEST_CONVERSATION_TYPE = u'sequential_send'

    def test_new_conversation(self):
        self.add_app_permission(u'go.apps.sequential_send')
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
        self.assertEqual(str(msg), "Sequential Send stopped")
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

    def test_start_with_group(self):
        """
        Test the start conversation view
        """
        self.setup_conversation(with_group=True, with_contact=True)

        response = self.client.post(self.get_view_url('start'))
        self.assertRedirects(response, self.get_view_url('show'))

        conversation = self.get_wrapped_conv()
        [contact] = self.get_contacts_for_conversation(conversation)

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

    def test_edit_conversation_schedule_config(self):
        self.setup_conversation()
        conversation = self.get_wrapped_conv()
        self.assertEqual(conversation.config, {})
        response = self.client.post(self.get_view_url('edit'), {
            'schedule-recurring': ['daily'],
            'schedule-days': [''],
            'schedule-time': ['12:00:00'],
            'messages-TOTAL_FORMS': ['1'],
            'messages-INITIAL_FORMS': ['0'],
            'messages-MAX_NUM_FORMS': [''],
            'messages-0-message': [''],
            'messages-0-DELETE': [''],
        })
        self.assertRedirects(response, self.get_view_url('show'))
        conversation = self.get_wrapped_conv()
        self.assertEqual(conversation.config, {
            u'messages': [],
            u'schedule': {
                u'recurring': u'daily',
                u'days': u'',
                u'time': u'12:00:00'}})
