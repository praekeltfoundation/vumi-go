from django.test import TestCase
from django.test.client import Client
from django.core.urlresolvers import reverse
from go.conversation.models import Conversation
from datetime import datetime


class ConversationTestCase(TestCase):

    fixtures = ['test_user']

    def setUp(self):
        self.client = Client()
        self.client.login(username='username', password='password')

    def tearDown(self):
        pass

    def test_new_conversation(self):
        """test the creationg of a new conversation"""
        # render the form
        self.assertFalse(Conversation.objects.exists())
        response = self.client.get(reverse('conversation:new'))
        self.assertEqual(response.status_code, 200)
        # post the form
        response = self.client.post(reverse('conversation:new'), {
            'subject': 'the subject',
            'message': 'the message',
            'start_date': datetime.utcnow().strftime('%Y-%m-%d'),
            'start_time': datetime.utcnow().strftime('%H:%M'),
        })
        self.assertTrue(Conversation.objects.exists())
