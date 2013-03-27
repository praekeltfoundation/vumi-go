from django.test.client import Client
from django.core.urlresolvers import reverse

from go.apps.tests.base import DjangoGoApplicationTestCase


class WikipediaTestCase(DjangoGoApplicationTestCase):

    def setUp(self):
        super(WikipediaTestCase, self).setUp()
        self.setup_riak_fixtures()
        self.client = Client()
        self.client.login(username='username', password='password')

    def test_new_conversation(self):
        # render the form
        self.assertEqual(len(self.conv_store.list_conversations()), 1)
        response = self.client.get(reverse('wikipedia_ussd:new'))
        self.assertEqual(response.status_code, 200)
        # post the form
        response = self.client.post(reverse('wikipedia_ussd:new'), {
            'subject': 'the subject',
            'message': 'the message',
            'delivery_class': 'sms',
            'delivery_tag_pool': 'longcode',
            'send_from_tagpool': 'devnull',
            'send_from_tag': '10017@devnull',
        })
        self.assertEqual(len(self.conv_store.list_conversations()), 2)
        conversation = self.get_latest_conversation()
        self.assertEqual(conversation.delivery_class, 'sms')
        self.assertEqual(conversation.delivery_tag_pool, 'longcode')
        self.assertEqual(conversation.delivery_tag, None)
        self.assertEqual(conversation.config, {
            'content': 'the message',
            'send_from_tagpool': 'devnull',
            'send_from_tag': '10017@devnull',
            })
        self.assertRedirects(response, reverse('wikipedia_ussd:start', kwargs={
            'conversation_key': conversation.key,
        }))
