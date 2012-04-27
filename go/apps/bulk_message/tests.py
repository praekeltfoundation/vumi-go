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


class BulkMessageTestCase(DjangoGoApplicationTestCase):

    fixtures = ['test_user', 'test_conversation',
                    'test_group', 'test_contact']

    def setUp(self):
        super(BulkMessageTestCase, self).setUp()
        self.client = Client()
        self.client.login(username='username', password='password')

        self.user = User.objects.get(username='username')
        self.conversation = self.user.conversation_set.latest()

    def test_new_conversation(self):
        """test the creation of a new conversation"""
        # render the form
        self.assertEqual(Conversation.objects.count(), 1)
        response = self.client.get(reverse('bulk_message:new'))
        self.assertEqual(response.status_code, 200)
        # post the form
        response = self.client.post(reverse('bulk_message:new'), {
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
        self.assertRedirects(response, reverse('bulk_message:people', kwargs={
            'conversation_pk': conversation.pk,
        }))

    def test_end(self):
        """
        Test ending the conversation
        """
        self.assertFalse(self.conversation.ended())
        response = self.client.post(reverse('bulk_message:end', kwargs={
            'conversation_pk': self.conversation.pk}), follow=True)
        self.assertRedirects(response, reverse('bulk_message:show', kwargs={
            'conversation_pk': self.conversation.pk}))
        [msg] = response.context['messages']
        self.assertEqual(str(msg), "Conversation ended")
        self.conversation = reload_record(self.conversation)
        self.assertTrue(self.conversation.ended())

    def test_group_selection(self):
        """Select an existing group and use that as the group for the
        conversation"""
        response = self.client.post(reverse('bulk_message:people',
            kwargs={'conversation_pk': self.conversation.pk}), {
            'groups': [grp.pk for grp in ContactGroup.objects.all()],
        })
        self.assertRedirects(response, reverse('bulk_message:send', kwargs={
            'conversation_pk': self.conversation.pk}))

    def test_send(self):
        """
        Test the start conversation view
        """

        response = self.client.post(reverse('bulk_message:send', kwargs={
            'conversation_pk': self.conversation.pk}))
        self.assertRedirects(response, reverse('bulk_message:show', kwargs={
            'conversation_pk': self.conversation.pk}))

        [batch] = self.conversation.message_batch_set.all()
        [contact] = self.conversation.people()
        conversation = self.conversation
        msg_options = {"from_addr": "default10001",
                       "transport_type": "sms"}

        [cmd] = self.get_api_commands_sent()
        self.assertEqual(cmd, VumiApiCommand.command(
            '%s_application' % (conversation.conversation_type,), 'start',
            conversation_type=self.conversation.conversation_type,
            conversation_id=self.conversation.pk,
            batch_id=batch.batch_id,
            msg_options=msg_options
            ))

    def test_send_fails(self):
        """
        Test failure to send messages
        """
        self.acquire_all_longcode_tags()
        consumer = self.get_cmd_consumer()
        response = self.client.post(reverse('bulk_message:send', kwargs={
            'conversation_pk': self.conversation.pk}), follow=True)
        self.assertRedirects(response, reverse('bulk_message:send', kwargs={
            'conversation_pk': self.conversation.pk}))
        [] = self.fetch_cmds(consumer)
        [] = self.conversation.preview_batch_set.all()
        [msg] = response.context['messages']
        self.assertEqual(str(msg), "No spare messaging tags.")

    def test_show(self):
        """
        Test showing the conversation
        """
        response = self.client.get(reverse('bulk_message:show', kwargs={
            'conversation_pk': self.conversation.pk}))
        conversation = response.context[0].get('conversation')
        self.assertEqual(conversation.subject, 'Test Conversation')
