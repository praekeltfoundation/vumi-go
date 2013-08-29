from go.apps.tests.base import DjangoGoApplicationTestCase


class SubscriptionTestCase(DjangoGoApplicationTestCase):
    TEST_CONVERSATION_TYPE = u'subscription'

    def test_new_conversation(self):
        self.add_app_permission(u'go.apps.subscription')
        self.assertEqual(len(self.conv_store.list_conversations()), 0)
        response = self.post_new_conversation()
        self.assertEqual(len(self.conv_store.list_conversations()), 1)
        conv = self.get_latest_conversation()
        self.assertRedirects(response, self.get_view_url('edit', conv.key))

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

    def test_content_block(self):
        # FIXME: This kind of thing probably belongs in generic view tests.
        self.setup_conversation()
        response = self.client.get(self.get_view_url('show'))
        self.assertContains(response, 'Content')
        self.assertContains(response, self.get_view_url('edit'))
