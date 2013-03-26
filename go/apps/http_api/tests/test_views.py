from django.test.client import Client
from django.core.urlresolvers import reverse

from go.apps.tests.base import DjangoGoApplicationTestCase


class HttpApiTestCase(DjangoGoApplicationTestCase):

    def setUp(self):
        super(HttpApiTestCase, self).setUp()
        self.setup_riak_fixtures()
        self.client = Client()
        self.client.login(username='username', password='password')

    def test_new_conversation(self):
        # render the form
        self.assertEqual(len(self.conv_store.list_conversations()), 1)
        response = self.client.get(reverse('http_api:new'))
        self.assertEqual(response.status_code, 200)
        # post the form
        response = self.client.post(reverse('http_api:new'), {
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
        self.assertEqual(conversation.config, {u'content': u'the message'})
        self.assertRedirects(response, reverse('http_api:people', kwargs={
            'conversation_key': conversation.key,
        }))

    def test_show_conversation(self):
        # render the form
        [conversation_key] = self.conv_store.list_conversations()
        kwargs = {'conversation_key': conversation_key}
        response = self.client.get(reverse('http_api:show', kwargs=kwargs))
        self.assertEqual(response.status_code, 200)
