from django.test import TestCase
from django.test.client import Client
from django.core.urlresolvers import reverse
from django.contrib.auth.models import User
from django.conf import settings
from go.conversation.models import Conversation
from go.contacts.models import ContactGroup, Contact
from go.base.utils import padded_queryset
from vumi.tests.utils import FakeRedis
from vumi.message import TransportUserMessage
from go.vumitools.tests.utils import CeleryTestMixIn, VumiApiCommand
from datetime import datetime
from os import path


def reload_record(record):
    return record.__class__.objects.get(pk=record.pk)


class SurveyTestCase(TestCase):

    fixtures = ['test_user', 'test_conversation']

    def setUp(self):
        self.client = Client()
        self.client.login(username='username', password='password')

        self.user = User.objects.get(username='username')
        self.conversation = self.user.conversation_set.latest()

    def tearDown(self):
        pass

    def test_new_conversation(self):
        """test the creation of a new conversation"""
        # render the form
        self.assertEqual(Conversation.objects.count(), 1)
        response = self.client.get(reverse('survey:new'))
        self.assertEqual(response.status_code, 200)
        # post the form
        response = self.client.post(reverse('survey:new'), {
            'subject': 'the subject',
            'message': 'the message',
            'start_date': datetime.utcnow().strftime('%Y-%m-%d'),
            'start_time': datetime.utcnow().strftime('%H:%M'),
            'delivery_class': 'sms',
            'delivery_tag_pool': 'longcode',
        })
        self.assertEqual(Conversation.objects.count(), 2)
        conversation = Conversation.objects.latest()
        self.assertEqual(conversation.delivery_class, 'sms')
        self.assertEqual(conversation.delivery_tag_pool, 'longcode')
        self.assertRedirects(response, reverse('survey:contents', kwargs={
            'conversation_pk': conversation.pk,
        }))

    def test_end(self):
        """
        Test ending the conversation
        """
        self.assertFalse(self.conversation.ended())
        response = self.client.post(reverse('survey:end', kwargs={
            'conversation_pk': self.conversation.pk}), follow=True)
        self.assertRedirects(response, reverse('survey:show', kwargs={
            'conversation_pk': self.conversation.pk}))
        [msg] = response.context['messages']
        self.assertEqual(str(msg), "Survey ended")
        self.conversation = reload_record(self.conversation)
        self.assertTrue(self.conversation.ended())

