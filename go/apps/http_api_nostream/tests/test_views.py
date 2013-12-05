from go.apps.tests.base import DjangoGoApplicationTestCase


class HttpApiNoStreamTestCase(DjangoGoApplicationTestCase):
    TEST_CONVERSATION_TYPE = u'http_api_nostream'

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

    def test_edit_view(self):
        self.setup_conversation(started=True)
        self.assertEqual(self.conversation.config, {})
        response = self.client.post(self.get_view_url('edit'), {
            'http_api_nostream-api_tokens': 'token',
            'http_api_nostream-push_message_url': 'http://messages/',
            'http_api_nostream-push_event_url': 'http://events/',
            })
        self.assertRedirects(response, self.get_view_url('show'))
        reloaded_conv = self.user_api.get_wrapped_conversation(
            self.conversation.key)
        self.assertEqual(reloaded_conv.config, {
            'http_api_nostream': {
                'push_event_url': 'http://events/',
                'push_message_url': 'http://messages/',
                'api_tokens': ['token'],
            }
        })
        self.assertEqual(self.conversation.config, {})
        response = self.client.get(self.get_view_url('edit'))
        self.assertContains(response, 'http://events/')
        self.assertContains(response, 'http://messages/')
        self.assertEqual(response.status_code, 200)

    def test_get_edit_view_no_config(self):
        self.setup_conversation(started=True)
        self.assertEqual(self.conversation.config, {})
        response = self.client.get(self.get_view_url('edit'))
        self.assertEqual(response.status_code, 200)
