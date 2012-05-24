from django.test.client import Client
from django.core.urlresolvers import reverse
from django.contrib.auth.models import User

from go.vumitools.contact import ContactStore
from go.vumitools.conversation import ConversationStore
from go.vumitools.tests.utils import VumiApiCommand
from go.apps.tests.base import DjangoGoApplicationTestCase
from go.base.utils import vumi_api_for_user


TEST_GROUP_NAME = u"Test Group"
TEST_CONTACT_NAME = u"Name"
TEST_CONTACT_SURNAME = u"Surname"
TEST_SUBJECT = u"Test Conversation"


class BulkMessageTestCase(DjangoGoApplicationTestCase):

    fixtures = ['test_user']

    def setUp(self):
        super(BulkMessageTestCase, self).setUp()
        self.client = Client()
        self.client.login(username='username', password='password')

        self.setup_riak_fixtures()

    def setup_riak_fixtures(self):
        self.user = User.objects.get(username='username')
        self.user_api = vumi_api_for_user(self.user)
        self.contact_store = self.user_api.contact_store
        self.contact_store.contacts.enable_search()
        self.conv_store = self.user_api.conversation_store

        # We need a group
        group = self.contact_store.new_group(TEST_GROUP_NAME)
        self.group_key = group.key

        # Also a contact
        contact = self.contact_store.new_contact(
            name=TEST_CONTACT_NAME, surname=TEST_CONTACT_SURNAME,
            msisdn=u"+27761234567")
        contact.add_to_group(group)
        contact.save()
        self.contact_key = contact.key

        # And a conversation
        conversation = self.conv_store.new_conversation(
            conversation_type=u'bulk_message', subject=TEST_SUBJECT,
            message=u"Test message", delivery_class=u"sms",
            delivery_tag_pool=u"longcode", groups=[self.group_key])
        self.conv_key = conversation.key

    def get_wrapped_conv(self):
        conv = self.conv_store.get_conversation_by_key(self.conv_key)
        return self.user_api.wrap_conversation(conv)

    def test_new_conversation(self):
        """test the creation of a new conversation"""
        # render the form
        self.assertEqual(len(self.conv_store.list_conversations()), 1)
        response = self.client.get(reverse('bulk_message:new'))
        self.assertEqual(response.status_code, 200)
        # post the form
        response = self.client.post(reverse('bulk_message:new'), {
            'subject': 'the subject',
            'message': 'the message',
            'delivery_class': 'sms',
            'delivery_tag_pool': 'longcode:',
        })
        self.assertEqual(len(self.conv_store.list_conversations()), 2)
        conversation = max(self.conv_store.list_conversations(),
                           key=lambda c: c.created_at)
        self.assertEqual(conversation.delivery_class, 'sms')
        self.assertEqual(conversation.delivery_tag_pool, 'longcode')
        self.assertEqual(conversation.delivery_tag, None)
        self.assertRedirects(response, reverse('bulk_message:people', kwargs={
            'conversation_key': conversation.key,
        }))

    def test_end(self):
        """
        Test ending the conversation
        """
        conversation = self.get_wrapped_conv()
        self.assertFalse(conversation.ended())
        response = self.client.post(reverse('bulk_message:end', kwargs={
            'conversation_key': conversation.key}), follow=True)
        self.assertRedirects(response, reverse('bulk_message:show', kwargs={
            'conversation_key': conversation.key}))
        [msg] = response.context['messages']
        self.assertEqual(str(msg), "Conversation ended")
        conversation = self.get_wrapped_conv()
        self.assertTrue(conversation.ended())

    def test_group_selection(self):
        """Select an existing group and use that as the group for the
        conversation"""
        response = self.client.post(reverse('bulk_message:people',
            kwargs={'conversation_key': self.conv_key}), {
            'groups': [grp.key for grp in self.contact_store.list_groups()],
        })
        self.assertRedirects(response, reverse('bulk_message:send', kwargs={
            'conversation_key': self.conv_key}))

    def test_start(self):
        """
        Test the start conversation view
        """
        conversation = self.get_wrapped_conv()

        response = self.client.post(reverse('bulk_message:send', kwargs={
            'conversation_key': conversation.key}))
        self.assertRedirects(response, reverse('bulk_message:show', kwargs={
            'conversation_key': conversation.key}))

        conversation = self.get_wrapped_conv()
        [batch] = conversation.get_batches()
        [tag] = list(batch.tags)
        [contact] = conversation.people()
        msg_options = {
            "transport_type": "sms",
            "from_addr": "default10001",
            "helper_metadata": {
                "tag": {"tag": list(tag)},
                "go": {"user_account": conversation.user_account.key},
                },
            }

        [cmd] = self.get_api_commands_sent()
        expected_cmd = VumiApiCommand.command(
            '%s_application' % (conversation.conversation_type,), 'start',
            batch_id=batch.key,
            msg_options=msg_options,
            conversation_type=conversation.conversation_type,
            conversation_key=conversation.key,
            is_client_initiated=conversation.is_client_initiated(),
            )
        self.assertEqual(cmd, expected_cmd)

    def test_send_fails(self):
        """
        Test failure to send messages
        """
        conversation = self.get_wrapped_conv()
        self.acquire_all_longcode_tags()
        consumer = self.get_cmd_consumer()
        response = self.client.post(reverse('bulk_message:send', kwargs={
            'conversation_key': conversation.key}), follow=True)
        self.assertRedirects(response, reverse('bulk_message:send', kwargs={
            'conversation_key': conversation.key}))
        [] = self.fetch_cmds(consumer)
        [msg] = response.context['messages']
        self.assertEqual(str(msg), "No spare messaging tags.")

    def test_show(self):
        """
        Test showing the conversation
        """
        response = self.client.get(reverse('bulk_message:show', kwargs={
            'conversation_key': self.conv_key}))
        conversation = response.context[0].get('conversation')
        self.assertEqual(conversation.subject, TEST_SUBJECT)
