from django.test.client import Client
from django.core.urlresolvers import reverse

from go.vumitools.tests.utils import VumiApiCommand
from go.apps.tests.base import DjangoGoApplicationTestCase
from go.base import message_store_client
from go.base.tests.utils import FakeMessageStoreClient

from vumi.tests.utils import mocking


class BulkMessageTestCase(DjangoGoApplicationTestCase):
    TEST_CONVERSATION_TYPE = u'bulk_message'

    def setUp(self):
        super(BulkMessageTestCase, self).setUp()
        self.setup_riak_fixtures()
        self.client = Client()
        self.client.login(username='username', password='password')

    def get_wrapped_conv(self):
        conv = self.conv_store.get_conversation_by_key(self.conv_key)
        return self.user_api.wrap_conversation(conv)

    def run_new_conversation(self, selected_option, pool, tag):
        # render the form
        self.assertEqual(len(self.conv_store.list_conversations()), 1)
        response = self.client.get(reverse('bulk_message:new'))
        self.assertEqual(response.status_code, 200)
        # post the form
        response = self.client.post(reverse('bulk_message:new'), {
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
        self.assertRedirects(response, reverse('bulk_message:people', kwargs={
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
            kwargs={'conversation_key': self.conv_key}), {'groups': [
                    grp.key for grp in self.contact_store.list_groups()]})
        self.assertRedirects(response, reverse('bulk_message:start', kwargs={
            'conversation_key': self.conv_key}))

    def test_start(self):
        """
        Test the start conversation view
        """
        conversation = self.get_wrapped_conv()

        response = self.client.post(reverse('bulk_message:start', kwargs={
            'conversation_key': conversation.key}))
        self.assertRedirects(response, reverse('bulk_message:show', kwargs={
            'conversation_key': conversation.key}))

        conversation = self.get_wrapped_conv()
        [batch] = conversation.get_batches()
        [tag] = list(batch.tags)
        [contact] = self.get_contacts_for_conversation(conversation)
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
            dedupe=False,
            msg_options=msg_options,
            conversation_type=conversation.conversation_type,
            conversation_key=conversation.key,
            is_client_initiated=conversation.is_client_initiated(),
            )
        self.assertEqual(cmd, expected_cmd)

    def test_start_with_deduplication(self):
        conversation = self.get_wrapped_conv()
        self.client.post(
            reverse('bulk_message:start', kwargs={
                    'conversation_key': conversation.key}),
            {'dedupe': '1'})
        [cmd] = self.get_api_commands_sent()
        self.assertEqual(cmd.payload['kwargs']['dedupe'], True)

    def test_start_without_deduplication(self):
        conversation = self.get_wrapped_conv()
        self.client.post(reverse('bulk_message:start', kwargs={
            'conversation_key': conversation.key}), {
        })
        [cmd] = self.get_api_commands_sent()
        self.assertEqual(cmd.payload['kwargs']['dedupe'], False)

    def test_send_fails(self):
        """
        Test failure to send messages
        """
        conversation = self.get_wrapped_conv()
        self.acquire_all_longcode_tags()
        consumer = self.get_cmd_consumer()
        response = self.client.post(reverse('bulk_message:start', kwargs={
            'conversation_key': conversation.key}), follow=True)
        self.assertRedirects(response, reverse('bulk_message:start', kwargs={
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
        self.assertEqual(conversation.subject, self.TEST_SUBJECT)

    def test_show_cached_message_pagination(self):
        # Create 21 inbound & 21 outbound messages, since we have
        # 20 messages per page it should give us 2 pages
        self.put_sample_messages_in_conversation(self.user_api,
                                                    self.conv_key, 21)
        response = self.client.get(reverse('bulk_message:show', kwargs={
            'conversation_key': self.conv_key}))

        # Check pagination
        # We should have 20 links to contacts which by default display
        # the from_addr if a contact cannot be found.
        self.assertContains(response, 'from-', 20)
        # We should have 2 links to page to, one for the actual page link
        # and one for the 'Next' page link
        self.assertContains(response, '&amp;p=2', 2)
        # There should only be 1 link to the current page
        self.assertContains(response, '&amp;p=1', 1)
        # There should not be a link to the previous page since we are not
        # the first page.
        self.assertContains(response, '&amp;p=0', 0)

    def test_show_cached_message_overview(self):
        self.put_sample_messages_in_conversation(self.user_api,
                                                    self.conv_key, 10)
        response = self.client.get(reverse('bulk_message:show', kwargs={
            'conversation_key': self.conv_key
            }))
        self.assertContains(response,
            '10 sent for delivery to the networks.')
        self.assertContains(response,
            '10 accepted for delivery by the networks.')
        self.assertContains(response, '10 delivered.')

    def test_message_search(self):
        fake_msc = FakeMessageStoreClient()

        with mocking(message_store_client.Client).to_return(fake_msc):
            response = self.client.get(reverse('bulk_message:show', kwargs={
                    'conversation_key': self.conv_key,
                }), {
                    'q': 'hello world 1',
                })

        template_names = [t.name for t in response.templates]
        self.assertTrue('generic/includes/message-load-results.html' in
                        template_names)
        self.assertEqual(response.context['token'], fake_msc.token)

    def test_message_results(self):
        fake_msc = FakeMessageStoreClient(
            results=[self.mkmsg_out() for i in range(10)], tries=2)

        fetch_results_url = reverse('bulk_message:results', kwargs={
                'conversation_key': self.conv_key,
            })
        fetch_results_params = {
            'q': 'hello world 1',
            'batch_id': 'batch-id',
            'direction': 'inbound',
            'token': fake_msc.token,
            'delay': 100,
        }

        with mocking(message_store_client.Client).to_return(fake_msc):
            response1 = self.client.get(fetch_results_url,
                                        fetch_results_params)
            response2 = self.client.get(fetch_results_url,
                                        fetch_results_params)

        # First time it should still show the loading page
        self.assertTrue('generic/includes/message-load-results.html' in
                            [t.name for t in response1.templates])
        self.assertEqual(response1.context['delay'], 1.1 * 100)
        # Second time it should still render the messages
        self.assertTrue('generic/includes/message-list.html' in
                            [t.name for t in response2.templates])
        self.assertEqual(response1.context['token'], fake_msc.token)
        # Second time we should list the matching messages
        self.assertEqual(response2.context['token'], fake_msc.token)
        self.assertEqual(len(response2.context['message_page'].object_list),
            10)
