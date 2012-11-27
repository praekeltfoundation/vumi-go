from django.test.client import Client
from django.core.urlresolvers import reverse

from go.apps.tests.base import DjangoGoApplicationTestCase


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
        self.assertEqual(conversation.delivery_class, 'sms')
        self.assertEqual(conversation.delivery_tag_pool, 'longcode')
        self.assertEqual(conversation.delivery_tag, None)
        self.assertEqual(conversation.metadata, None)
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
        })
        self.assertRedirects(response, reverse('jsbox:people', kwargs=kwargs))
        conversation = self.get_latest_conversation()
        self.assertEqual(conversation.metadata, {
            'jsbox': {
                    'javascript': 'x = 1;',
                    'source_url': '',
            },
        })
