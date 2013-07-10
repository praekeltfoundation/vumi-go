from go.apps.tests.base import DjangoGoApplicationTestCase


class HttpApiTestCase(DjangoGoApplicationTestCase):
    TEST_CONVERSATION_TYPE = u'http_api'

    def test_new_conversation(self):
        self.add_app_permission(u'go.apps.http_api')
        self.assertEqual(len(self.conv_store.list_conversations()), 0)
        response = self.post_new_conversation()
        self.assertEqual(len(self.conv_store.list_conversations()), 1)
        conversation = self.get_latest_conversation()
        self.assertEqual(conversation.name, 'conversation name')
        self.assertEqual(conversation.description, '')
        self.assertEqual(conversation.config, {})
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
