from go.apps.tests.base import DjangoGoApplicationTestCase


class SequentialSendTestCase(DjangoGoApplicationTestCase):
    TEST_CONVERSATION_TYPE = u'sequential_send'

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
