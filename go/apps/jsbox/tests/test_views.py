import logging

from go.apps.tests.base import DjangoGoApplicationTestCase
from go.apps.jsbox.log import LogManager

from mock import patch, Mock


class JsBoxTestCase(DjangoGoApplicationTestCase):
    TEST_CONVERSATION_TYPE = u'jsbox'

    def test_new_conversation(self):
        self.assertEqual(len(self.conv_store.list_conversations()), 0)
        response = self.post_new_conversation()
        self.assertEqual(len(self.conv_store.list_conversations()), 1)
        conversation = self.get_latest_conversation()
        self.assertEqual(conversation.name, 'conversation name')
        self.assertEqual(conversation.description, '')
        self.assertEqual(conversation.config, {})
        self.assertRedirects(
            response, self.get_view_url('edit', conversation.key))

    def test_show_stopped(self):
        self.setup_conversation()
        response = self.client.get(self.get_view_url('show'))
        conversation = response.context[0].get('conversation')
        self.assertEqual(conversation.name, self.TEST_CONVERSATION_NAME)

    def test_show_running(self):
        self.setup_conversation(started=True)
        response = self.client.get(self.get_view_url('show'))
        conversation = response.context[0].get('conversation')
        self.assertEqual(conversation.name, self.TEST_CONVERSATION_NAME)

    def test_edit_conversation(self):
        self.setup_conversation()
        # render the form
        response = self.client.get(self.get_view_url('edit'))
        self.assertEqual(response.status_code, 200)
        # post the form
        response = self.client.post(self.get_view_url('edit'), {
            'jsbox-javascript': 'x = 1;',
            'jsbox-source_url': '',
            'jsbox-update_from_source': '0',
            'jsbox_app_config-TOTAL_FORMS': '1',
            'jsbox_app_config-INITIAL_FORMS': '0',
            'jsbox_app_config-MAX_NUM_FORMS': u''
        })
        self.assertRedirects(response, self.get_view_url('show'))
        conversation = self.get_wrapped_conv()
        self.assertEqual(conversation.config, {
            'jsbox': {
                    'javascript': 'x = 1;',
                    'source_url': '',
            },
            'jsbox_app_config': {},
        })

    @patch('requests.get')
    def test_cross_domain_xhr(self, mocked_get):
        self.setup_conversation()
        mocked_get.return_value = Mock(text='foo', status_code=200)
        response = self.client.post(
            self.get_view_url('cross_domain_xhr'),
            {'url': 'http://domain.com'})
        [call] = mocked_get.call_args_list
        args, kwargs = call
        self.assertEqual(args, ('http://domain.com',))
        self.assertEqual(kwargs, {'auth': None})
        self.assertTrue(mocked_get.called)
        self.assertEqual(response.content, 'foo')
        self.assertEqual(response.status_code, 200)

    @patch('requests.get')
    def test_basic_auth_cross_domain_xhr(self, mocked_get):
        self.setup_conversation()
        mocked_get.return_value = Mock(text='foo', status_code=200)
        response = self.client.post(
            self.get_view_url('cross_domain_xhr'),
            {'url': 'http://username:password@domain.com'})
        [call] = mocked_get.call_args_list
        args, kwargs = call
        self.assertEqual(args, ('http://domain.com',))
        self.assertEqual(kwargs, {'auth': ('username', 'password')})
        self.assertTrue(mocked_get.called)
        self.assertEqual(response.content, 'foo')
        self.assertEqual(response.status_code, 200)

    @patch('requests.get')
    def test_basic_auth_cross_domain_xhr_with_https_and_port(self, mocked_get):
        self.setup_conversation()
        mocked_get.return_value = Mock(text='foo', status_code=200)
        response = self.client.post(
            self.get_view_url('cross_domain_xhr'),
            {'url': 'https://username:password@domain.com:443/foo'})
        [call] = mocked_get.call_args_list
        args, kwargs = call
        self.assertEqual(args, ('https://domain.com:443/foo',))
        self.assertEqual(kwargs, {'auth': ('username', 'password')})
        self.assertTrue(mocked_get.called)
        self.assertEqual(response.content, 'foo')
        self.assertEqual(response.status_code, 200)

    def test_jsbox_logs(self):
        self.setup_conversation()
        campaign_key = self.user_api.user_account_key
        log_manager = LogManager(self.user_api.api.redis)
        for i in range(10):
            log_manager.add_log(campaign_key, self.conv_key,
                                "test %d" % i, logging.INFO)
        response = self.client.get(self.get_view_url('jsbox_logs'))
        self.assertEqual(response.status_code, 200)
        for i in range(10):
            self.assertContains(response, "INFO] test %d" % i)

    def test_jsbox_empty_logs(self):
        self.setup_conversation()
        response = self.client.get(self.get_view_url('jsbox_logs'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No logs yet.")

    def test_jsbox_logs_action(self):
        self.setup_conversation()
        response = self.client.get(self.get_action_view_url('view_logs'))
        self.assertRedirects(response, self.get_view_url('jsbox_logs'))
