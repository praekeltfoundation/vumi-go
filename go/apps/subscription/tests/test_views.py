from django.test.client import Client
from django.core.urlresolvers import reverse

from go.vumitools.tests.utils import VumiApiCommand
from go.apps.tests.base import DjangoGoApplicationTestCase


class SubscriptionTestCase(DjangoGoApplicationTestCase):
    TEST_CONVERSATION_TYPE = u'subscription'

    def setUp(self):
        super(SubscriptionTestCase, self).setUp()
        self.setup_riak_fixtures()
        self.client = Client()
        self.client.login(username='username', password='password')

    def get_wrapped_conv(self):
        conv = self.conv_store.get_conversation_by_key(self.conv_key)
        return self.user_api.wrap_conversation(conv)

    def run_new_conversation(self, selected_option, pool, tag):
        # render the form
        self.assertEqual(len(self.conv_store.list_conversations()), 1)
        response = self.client.get(reverse('subscription:new'))
        self.assertEqual(response.status_code, 200)
        # post the form
        response = self.client.post(reverse('subscription:new'), {
            'subject': 'the subject',
            'message': 'the message',
            'delivery_class': 'sms',
            'delivery_tag_pool': selected_option,
        })
        self.assertEqual(len(self.conv_store.list_conversations()), 2)
        conversation = self.get_latest_conversation()
        self.assertEqual(conversation.delivery_class, 'sms')
        self.assertEqual(conversation.delivery_tag_pool, pool)
        self.assertEqual(conversation.delivery_tag, tag)
        self.assertRedirects(response, reverse('subscription:edit', kwargs={
            'conversation_key': conversation.key,
        }))

    def test_new_conversation(self):
        """test the creation of a new conversation"""
        self.run_new_conversation('longcode:', 'longcode', None)

    def test_new_conversation_with_user_selected_tags(self):
        tp_meta = self.api.tpm.get_metadata('longcode')
        tp_meta['user_selects_tag'] = True
        self.api.tpm.set_metadata('longcode', tp_meta)
        self.run_new_conversation('longcode:default10001', 'longcode',
                                  'default10001')

    def test_end(self):
        """
        Test ending the conversation
        """
        conversation = self.get_wrapped_conv()
        self.assertFalse(conversation.ended())
        response = self.client.post(reverse('subscription:end', kwargs={
            'conversation_key': conversation.key}), follow=True)
        self.assertRedirects(response, reverse('subscription:show', kwargs={
            'conversation_key': conversation.key}))
        [msg] = response.context['messages']
        self.assertEqual(str(msg), "Conversation ended")
        conversation = self.get_wrapped_conv()
        self.assertTrue(conversation.ended())

    def test_start(self):
        """
        Test the start conversation view
        """
        conversation = self.get_wrapped_conv()

        response = self.client.post(reverse('subscription:start', kwargs={
            'conversation_key': conversation.key}))
        self.assertRedirects(response, reverse('subscription:show', kwargs={
            'conversation_key': conversation.key}))

        conversation = self.get_wrapped_conv()
        [batch] = conversation.get_batches()
        [tag] = list(batch.tags)
        [contact] = self.get_contacts_for_conversation(conversation)
        msg_options = {
            "transport_type": "sms",
            "transport_name": self.transport_name,
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
        response = self.client.post(reverse('subscription:start', kwargs={
            'conversation_key': conversation.key}), follow=True)
        self.assertRedirects(response, reverse('subscription:start', kwargs={
            'conversation_key': conversation.key}))
        [] = self.fetch_cmds(consumer)
        [msg] = response.context['messages']
        self.assertEqual(str(msg), "No spare messaging tags.")

    def test_show(self):
        """
        Test showing the conversation
        """
        response = self.client.get(reverse('subscription:show', kwargs={
            'conversation_key': self.conv_key}))
        conversation = response.context[0].get('conversation')
        self.assertEqual(conversation.name, self.TEST_CONVERSATION_NAME)
