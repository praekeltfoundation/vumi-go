from django.test.client import Client
from django.core.urlresolvers import reverse

from go.apps.tests.base import DjangoGoApplicationTestCase
from go.base.utils import get_conversation_definition
from go.conversation.conversation_views import ConversationViewFinder


class HttpApiTestCase(DjangoGoApplicationTestCase):

    TEST_CONVERSATION_TYPE = u'http_api'

    def setUp(self):
        super(HttpApiTestCase, self).setUp()
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
            'conversation_type': self.TEST_CONVERSATION_TYPE})

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
        conversation = self.get_latest_conversation()
        self.assertEqual(conversation.delivery_class, 'sms')
        self.assertEqual(conversation.delivery_tag_pool, 'longcode')
        self.assertEqual(conversation.delivery_tag, None)
        self.assertEqual(conversation.name, 'the subject')
        self.assertEqual(conversation.description, 'the message')
        self.assertEqual(conversation.config, {})
        self.assertRedirects(
            response, self.get_view_url('people', conversation.key))

    def test_show_conversation(self):
        # render the form
        [conversation_key] = self.conv_store.list_conversations()
        response = self.client.get(self.get_view_url('show'))
        self.assertEqual(response.status_code, 200)
