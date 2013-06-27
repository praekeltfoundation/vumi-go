from django.test.client import Client
from django.core.urlresolvers import reverse

from go.apps.tests.base import DjangoGoApplicationTestCase
from go.base.utils import get_conversation_view_definition


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
        view_def = get_conversation_view_definition(
            self.TEST_CONVERSATION_TYPE)
        return view_def.get_view_url(view, conversation_key=conv_key)

    def get_new_view_url(self):
        return reverse('conversations:new_conversation')

    def test_new_conversation(self):
        self.assertEqual(len(self.conv_store.list_conversations()), 1)
        response = self.post_new_conversation()
        self.assertEqual(len(self.conv_store.list_conversations()), 2)
        conversation = self.get_latest_conversation()
        self.assertEqual(conversation.name, 'conversation name')
        self.assertEqual(conversation.description, '')
        self.assertEqual(conversation.config, {})
        self.assertRedirects(
            response, self.get_view_url('show', conversation.key))

    def test_show_conversation(self):
        # render the form
        [conversation_key] = self.conv_store.list_conversations()
        response = self.client.get(self.get_view_url('show'))
        self.assertEqual(response.status_code, 200)
