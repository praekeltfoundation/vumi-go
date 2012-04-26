from datetime import datetime

from django.test.client import Client
from django.core.urlresolvers import reverse
from django.contrib.auth.models import User

from go.conversation.models import Conversation
from go.contacts.models import ContactGroup
from go.vumitools.tests.utils import VumiApiCommand
from go.apps.tests.base import DjangoGoApplicationTestCase


def reload_record(record):
    return record.__class__.objects.get(pk=record.pk)


class SurveyTestCase(DjangoGoApplicationTestCase):

    fixtures = ['test_user', 'test_conversation',
                    'test_group', 'test_contact']

    def setUp(self):
        super(SurveyTestCase, self).setUp()
        self.client = Client()
        self.client.login(username='username', password='password')

        self.user = User.objects.get(username='username')
        self.conversation = self.user.conversation_set.latest()

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

    def test_client_or_server_init_distinction(self):
        """A survey should not ask for recipients if the transport
        used only supports client initiated sessions (i.e. USSD)"""
        def render_people_page(delivery_class):
            self.conversation.delivery_class = delivery_class
            self.conversation.save()
            return self.client.get(reverse('survey:people', kwargs={
                'conversation_pk': self.conversation.pk,
                }))

        self.assertContains(render_people_page('sms'), 'Survey Recipients')
        self.assertNotContains(render_people_page('ussd'), 'Survey Recipients')

    def test_group_selection(self):
        """Select an existing group and use that as the group for the
        conversation"""
        self.assertFalse(self.conversation.is_client_initiated())
        response = self.client.post(reverse('survey:people',
            kwargs={'conversation_pk': self.conversation.pk}), {
            'groups': [grp.pk for grp in ContactGroup.objects.all()],
        })
        self.assertRedirects(response, reverse('survey:start', kwargs={
            'conversation_pk': self.conversation.pk}))

    def test_start(self):
        """
        Test the start conversation view
        """
        consumer = self.get_cmd_consumer()

        response = self.client.post(reverse('survey:start', kwargs={
            'conversation_pk': self.conversation.pk}))
        self.assertRedirects(response, reverse('survey:show', kwargs={
            'conversation_pk': self.conversation.pk}))

        [cmd] = self.fetch_cmds(consumer)
        [batch] = self.conversation.message_batch_set.all()
        [contact] = self.conversation.people()
        conversation = self.conversation
        msg_options = {"from_addr": "default10001",
                       "transport_type": "sms",
                       "transport_name": "smpp_transport",
                       "worker_name": "bulk_message_application",
                       "conversation_id": conversation.pk,
                       "conversation_type": conversation.conversation_type,
                       }
        self.assertEqual(cmd, VumiApiCommand.send(batch.batch_id,
                                                  "",
                                                  msg_options,
                                                  contact.msisdn))

    def test_send_fails(self):
        """
        Test failure to send messages
        """
        self.acquire_all_longcode_tags()
        consumer = self.get_cmd_consumer()
        response = self.client.post(reverse('survey:start', kwargs={
            'conversation_pk': self.conversation.pk}), follow=True)
        self.assertRedirects(response, reverse('survey:start', kwargs={
            'conversation_pk': self.conversation.pk}))
        [] = self.fetch_cmds(consumer)
        [] = self.conversation.preview_batch_set.all()
        [msg] = response.context['messages']
        self.assertEqual(str(msg), "No spare messaging tags.")

    def test_show(self):
        """
        Test showing the conversation
        """
        response = self.client.get(reverse('survey:show', kwargs={
            'conversation_pk': self.conversation.pk}))
        conversation = response.context[0].get('conversation')
        self.assertEqual(conversation.subject, 'Test Conversation')
