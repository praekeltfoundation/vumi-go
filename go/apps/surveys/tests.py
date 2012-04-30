from datetime import datetime

from django.test.client import Client
from django.core.urlresolvers import reverse
from django.contrib.auth.models import User

from go.vumitools.contact import ContactStore
from go.vumitools.conversation import ConversationStore
from go.vumitools.tests.utils import VumiApiCommand
from go.apps.tests.base import DjangoGoApplicationTestCase


TEST_GROUP_NAME = u"Test Group"
TEST_CONTACT_NAME = u"Name"
TEST_CONTACT_SURNAME = u"Surname"
TEST_SUBJECT = u"Test Conversation"


class SurveyTestCase(DjangoGoApplicationTestCase):

    fixtures = ['test_user']

    def setUp(self):
        super(SurveyTestCase, self).setUp()
        self.client = Client()
        self.client.login(username='username', password='password')

        self.setup_riak_fixtures()

    def setup_riak_fixtures(self):
        self.user = User.objects.get(username='username')
        self.contact_store = ContactStore.from_django_user(self.user)
        self.contact_store.contacts.enable_search()
        self.conv_store = ConversationStore.from_django_user(self.user)
        group = self.contact_store.new_group(TEST_GROUP_NAME)
        contact = self.contact_store.new_contact(
            name=TEST_CONTACT_NAME, surname=TEST_CONTACT_SURNAME,
            msisdn=u"+27761234567")
        contact.add_to_group(group)
        contact.save()
        self.contact_key = contact.key
        conversation = self.conv_store.new_conversation(
            conversation_type=u'bulk_message', subject=TEST_SUBJECT,
            message=u"Test message", delivery_class=u"sms",
            delivery_tag_pool=u"longcode", groups=[TEST_GROUP_NAME])
        self.conv_key = conversation.key

    def get_wrapped_conv(self):
        conv = self.conv_store.get_conversation_by_key(self.conv_key)
        return self.api.wrap_conversation(conv)

    def test_new_conversation(self):
        """test the creation of a new conversation"""
        # render the form
        self.assertEqual(len(self.conv_store.list_conversations()), 1)
        response = self.client.get(reverse('survey:new'))
        self.assertEqual(response.status_code, 200)
        # post the form
        response = self.client.post(reverse('survey:new'), {
            'subject': 'the subject',
            'message': 'the message',
            # 'start_date': datetime.utcnow().strftime('%Y-%m-%d'),
            # 'start_time': datetime.utcnow().strftime('%H:%M'),
            'delivery_class': 'sms',
            'delivery_tag_pool': 'longcode',
        })
        self.assertEqual(len(self.conv_store.list_conversations()), 2)
        conversation = max(self.conv_store.list_conversations(),
                           key=lambda c: c.created_at)
        self.assertEqual(conversation.delivery_class, 'sms')
        self.assertEqual(conversation.delivery_tag_pool, 'longcode')
        self.assertRedirects(response, reverse('survey:contents', kwargs={
            'conversation_key': conversation.key,
        }))

    def test_end(self):
        """
        Test ending the conversation
        """
        conversation = self.get_wrapped_conv()
        self.assertFalse(conversation.ended())
        response = self.client.post(reverse('survey:end', kwargs={
            'conversation_key': conversation.key}), follow=True)
        self.assertRedirects(response, reverse('survey:show', kwargs={
            'conversation_key': conversation.key}))
        [msg] = response.context['messages']
        self.assertEqual(str(msg), "Survey ended")
        conversation = self.get_wrapped_conv()
        self.assertTrue(conversation.ended())

    def test_client_or_server_init_distinction(self):
        """A survey should not ask for recipients if the transport
        used only supports client initiated sessions (i.e. USSD)"""
        def get_people_page(delivery_class):
            conversation = self.get_wrapped_conv()
            conversation.c.delivery_class = delivery_class
            conversation.save()
            return self.client.get(reverse('survey:people', kwargs={
                'conversation_key': conversation.key,
                }))

        self.assertContains(get_people_page(u'sms'), 'Survey Recipients')
        self.assertNotContains(get_people_page(u'ussd'), 'Survey Recipients')

    def test_group_selection(self):
        """Select an existing group and use that as the group for the
        conversation"""
        conversation = self.get_wrapped_conv()
        self.assertFalse(conversation.is_client_initiated())
        response = self.client.post(reverse('survey:people',
            kwargs={'conversation_key': conversation.key}), {
            'groups': [grp.key for grp in self.contact_store.list_groups()],
        })
        self.assertRedirects(response, reverse('survey:start', kwargs={
            'conversation_key': conversation.key}))

    def test_start(self):
        """
        Test the start conversation view
        """
        consumer = self.get_cmd_consumer()

        response = self.client.post(reverse('survey:start', kwargs={
            'conversation_key': self.conv_key}))
        self.assertRedirects(response, reverse('survey:show', kwargs={
            'conversation_key': self.conv_key}))

        conversation = self.get_wrapped_conv()
        [cmd] = self.fetch_cmds(consumer)
        [batch] = conversation.get_batches()
        [contact] = conversation.people()
        msg_options = {"from_addr": "default10001",
                       "transport_type": "sms",
                       }

        self.assertEqual(cmd, VumiApiCommand.command(
            '%s_application' % (conversation.conversation_type,), 'start',
            conversation_type=conversation.conversation_type,
            conversation_id=conversation.key,
            batch_id=batch.key,
            msg_options=msg_options
            ))

    def test_send_fails(self):
        """
        Test failure to send messages
        """
        self.acquire_all_longcode_tags()
        consumer = self.get_cmd_consumer()
        response = self.client.post(reverse('survey:start', kwargs={
            'conversation_key': self.conv_key}), follow=True)
        self.assertRedirects(response, reverse('survey:start', kwargs={
            'conversation_key': self.conv_key}))
        [] = self.fetch_cmds(consumer)
        [msg] = response.context['messages']
        self.assertEqual(str(msg), "No spare messaging tags.")

    def test_show(self):
        """
        Test showing the conversation
        """
        response = self.client.get(reverse('survey:show', kwargs={
            'conversation_key': self.conv_key}))
        conversation = response.context[0].get('conversation')
        self.assertEqual(conversation.subject, 'Test Conversation')
