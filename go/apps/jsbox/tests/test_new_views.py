import logging

from django.test.client import Client
from django.core.urlresolvers import reverse

from go.base.utils import get_conversation_definition
from go.conversation.conversation_views import ConversationViewFinder
from go.apps.tests.base import DjangoGoApplicationTestCase
from go.apps.jsbox.log import LogManager
from go.apps.jsbox.views import JsboxConversationViews

from mock import patch, Mock


class JsBoxTestCase(DjangoGoApplicationTestCase):

    VIEWS_CLASS = JsboxConversationViews

    def setUp(self):
        super(JsBoxTestCase, self).setUp()
        self.setup_riak_fixtures()
        self.client = Client()
        self.client.login(username='username', password='password')

    def get_view_url(self, view, conv_key=None):
        if conv_key is None:
            conv_key = self.conv_key
        conv_def = get_conversation_definition(self.TEST_CONVERSATION_TYPE)
        finder = ConversationViewFinder(conv_def(None))
        return finder.get_view_url(view, conversation_key=conv_key)

    def get_new_view_url(self):
        return reverse('conversations:new_conversation', kwargs={
            'conversation_type': self.VIEWS_CLASS.conversation_type})

    def get_action_view_url(self, action_name, conv_key=None):
        if conv_key is None:
            conv_key = self.conv_key
        return reverse('conversations:conversation_action', kwargs={
            'conversation_key': conv_key, 'action_name': action_name})

    def test_new_conversation(self):
        # render the form
        self.assertEqual(len(self.conv_store.list_conversations()), 1)
        response = self.client.get(self.get_new_view_url())
        self.assertEqual(response.status_code, 200)
        # post the form
        response = self.client.post(self.get_new_view_url(), {
            'subject': 'the subject',
            'message': 'the message',
            'delivery_class': 'sms',
            'delivery_tag_pool': 'longcode',
        })
        self.assertEqual(len(self.conv_store.list_conversations()), 2)
        conv = self.get_latest_conversation()
        self.assertEqual(conv.name, 'the subject')
        self.assertEqual(conv.description, 'the message')
        self.assertEqual(conv.delivery_class, 'sms')
        self.assertEqual(conv.delivery_tag_pool, 'longcode')
        self.assertEqual(conv.delivery_tag, None)
        self.assertEqual(conv.config, {})
        self.assertRedirects(response, self.get_view_url('edit', conv.key))

    def test_show_conversation(self):
        [conversation_key] = self.conv_store.list_conversations()
        response = self.client.get(self.get_view_url('show'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "View Sandbox Logs")
        self.assertContains(response, self.get_action_view_url('view_logs'))

    def test_edit_conversation(self):
        # render the form
        [conversation_key] = self.conv_store.list_conversations()
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
        self.assertRedirects(response, self.get_view_url('people'))
        conversation = self.get_latest_conversation()
        self.assertEqual(conversation.config, {
            'jsbox': {
                    'javascript': 'x = 1;',
                    'source_url': '',
            },
            'jsbox_app_config': {},
        })

    @patch('requests.get')
    def test_cross_domain_xhr(self, mocked_get):
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
        campaign_key = self.user_api.user_account_key
        [conversation_key] = self.conv_store.list_conversations()
        log_manager = LogManager(self.user_api.api.redis)
        for i in range(10):
            log_manager.add_log(campaign_key, conversation_key,
                                "test %d" % i, logging.INFO)
        response = self.client.get(self.get_view_url('jsbox_logs'))
        self.assertEqual(response.status_code, 200)
        for i in range(10):
            self.assertContains(response, "INFO] test %d" % i)

    def test_jsbox_empty_logs(self):
        [conversation_key] = self.conv_store.list_conversations()
        response = self.client.get(self.get_view_url('jsbox_logs'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No logs yet.")

    def test_jsbox_logs_action(self):
        response = self.client.get(self.get_action_view_url('view_logs'))
        self.assertRedirects(response, self.get_view_url('jsbox_logs'))
