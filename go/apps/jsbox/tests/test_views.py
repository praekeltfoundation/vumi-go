import logging

from django.test.client import Client
from django.core.urlresolvers import reverse

from go.apps.tests.base import DjangoGoApplicationTestCase
from go.apps.jsbox.log import LogManager

from mock import patch, Mock


class JsBoxTestCase(DjangoGoApplicationTestCase):

    def setUp(self):
        super(JsBoxTestCase, self).setUp()
        self.setup_riak_fixtures()
        self.client = Client()
        self.client.login(username='username', password='password')

    def test_new_conversation(self):
        # render the form
        self.assertEqual(len(self.conv_store.list_conversations()), 1)
        response = self.client.get(reverse('jsbox:new'))
        self.assertEqual(response.status_code, 200)
        # post the form
        response = self.client.post(reverse('jsbox:new'), {
            'subject': 'the subject',
            'message': 'the message',
            'delivery_class': 'sms',
            'delivery_tag_pool': 'longcode',
        })
        self.assertEqual(len(self.conv_store.list_conversations()), 2)
        conversation = self.get_latest_conversation()
        self.assertEqual(conversation.name, 'the subject')
        self.assertEqual(conversation.description, 'the message')
        self.assertEqual(conversation.delivery_class, 'sms')
        self.assertEqual(conversation.delivery_tag_pool, 'longcode')
        self.assertEqual(conversation.delivery_tag, None)
        self.assertEqual(conversation.config, {})
        self.assertRedirects(response, reverse('jsbox:edit', kwargs={
            'conversation_key': conversation.key,
        }))

    def test_edit_conversation(self):
        # render the form
        [conversation_key] = self.conv_store.list_conversations()
        kwargs = {'conversation_key': conversation_key}
        response = self.client.get(reverse('jsbox:edit', kwargs=kwargs))
        self.assertEqual(response.status_code, 200)
        # post the form
        response = self.client.post(reverse('jsbox:edit', kwargs=kwargs), {
            'jsbox-javascript': 'x = 1;',
            'jsbox-source_url': '',
            'jsbox-update_from_source': '0',
            'jsbox_app_config-TOTAL_FORMS': '1',
            'jsbox_app_config-INITIAL_FORMS': '0',
            'jsbox_app_config-MAX_NUM_FORMS': u''
        })
        self.assertRedirects(response, reverse('jsbox:people', kwargs=kwargs))
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
            reverse('jsbox:cross_domain_xhr'),
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
            reverse('jsbox:cross_domain_xhr'),
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
            reverse('jsbox:cross_domain_xhr'),
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
        log_manager = LogManager(self.user_api.api.redis.sub_manager(
            "jsbox_logs_store"))
        for i in range(10):
            log_manager.add_log(campaign_key, conversation_key,
                                "test %d" % i, logging.INFO)
        kwargs = {'conversation_key': conversation_key}
        response = self.client.get(reverse('jsbox:jsbox_logs', kwargs=kwargs))
        self.assertEqual(response.status_code, 200)
        for i in range(10):
            self.assertContains(response, "INFO] test %d" % i)

    def test_jsbox_empty_logs(self):
        [conversation_key] = self.conv_store.list_conversations()
        kwargs = {'conversation_key': conversation_key}
        response = self.client.get(reverse('jsbox:jsbox_logs', kwargs=kwargs))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No logs yet.")
