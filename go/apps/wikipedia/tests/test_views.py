from go.apps.tests.base import DjangoGoApplicationTestCase


class WikipediaTestCase(DjangoGoApplicationTestCase):
    TEST_CONVERSATION_TYPE = u'wikipedia'

    def test_new_conversation(self):
        """Ensure that the newly created conversation has the right endpoints.
        """
        self.add_app_permission(u'go.apps.wikipedia')
        self.assertEqual(len(self.conv_store.list_conversations()), 0)
        response = self.post_new_conversation()
        self.assertEqual(len(self.conv_store.list_conversations()), 1)
        conversation = self.get_latest_conversation()
        self.assertEqual(conversation.name, 'conversation name')
        self.assertEqual(conversation.description, '')
        self.assertEqual(conversation.config, {})
        self.assertEqual(list(conversation.extra_endpoints), [u'sms_content'])
        self.assertRedirects(
            response, self.get_view_url('show', conversation.key))

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
