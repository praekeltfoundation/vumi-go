from datetime import date

from django.test.client import Client
from django.core import mail
from django.core.urlresolvers import reverse
from django.utils.unittest import skip

from vumi.tests.utils import RegexMatcher

from go.vumitools.tests.utils import VumiApiCommand
from go.vumitools.token_manager import TokenManager
from go.base.utils import get_conversation_view_definition
from go.apps.tests.base import DjangoGoApplicationTestCase
from go.base.tests.utils import FakeMessageStoreClient, FakeMatchResult

from mock import patch


class BulkMessageTestCase(DjangoGoApplicationTestCase):
    TEST_CONVERSATION_TYPE = u'bulk_message'

    def setUp(self):
        super(BulkMessageTestCase, self).setUp()
        self.setup_riak_fixtures()
        self.client = Client()
        self.client.login(username='username', password='password')

    def get_view_url(self, view, conv_key=None):
        if conv_key is None:
            conv_key = self.conv_key
        view_def = get_conversation_view_definition(
            self.TEST_CONVERSATION_TYPE)
        return view_def.get_view_url(view, conversation_key=conv_key)

    def get_new_view_url(self):
        return reverse('conversations:new_conversation')

    def get_action_view_url(self, action_name, conv_key=None):
        if conv_key is None:
            conv_key = self.conv_key
        return reverse('conversations:conversation_action', kwargs={
            'conversation_key': conv_key, 'action_name': action_name})

    def get_wrapped_conv(self):
        conv = self.conv_store.get_conversation_by_key(self.conv_key)
        return self.user_api.wrap_conversation(conv)

    def run_new_conversation(self, selected_option, pool, tag):
        self.assertEqual(len(self.conv_store.list_conversations()), 1)
        response = self.post_new_conversation()
        self.assertEqual(len(self.conv_store.list_conversations()), 2)
        conv = self.get_latest_conversation()
        self.assertRedirects(response, self.get_view_url('show', conv.key))

    def test_new_conversation(self):
        """test the creation of a new conversation"""
        self.run_new_conversation('longcode:', 'longcode', None)

    def test_new_conversation_with_user_selected_tags(self):
        tp_meta = self.api.tpm.get_metadata('longcode')
        tp_meta['user_selects_tag'] = True
        self.api.tpm.set_metadata(u'longcode', tp_meta)
        self.run_new_conversation(u'longcode:default10001', u'longcode',
                                  u'default10001')

    def test_stop(self):
        """
        Test ending the conversation
        """
        conversation = self.get_wrapped_conv()
        conversation.set_status_started()
        conversation.save()
        response = self.client.post(self.get_view_url('stop'), follow=True)
        self.assertRedirects(response, self.get_view_url('show'))
        [msg] = response.context['messages']
        self.assertEqual(str(msg), "Conversation stopped")
        conversation = self.get_wrapped_conv()
        self.assertTrue(conversation.stopping())

    @skip("The new views don't have this yet.")
    def test_group_selection(self):
        """Select an existing group and use that as the group for the
        conversation"""
        response = self.client.post(self.get_view_url('people'), {'groups': [
            grp.key for grp in self.contact_store.list_groups()]})
        self.assertRedirects(response, self.get_view_url('start'))

    def test_start(self):
        """
        Test the start conversation view
        """
        conversation = self.get_wrapped_conv()

        response = self.client.post(self.get_view_url('start'))
        self.assertRedirects(response, self.get_view_url('show'))

        conversation = self.get_wrapped_conv()
        [batch] = conversation.get_batches()
        [tag] = list(batch.tags)
        [contact] = self.get_contacts_for_conversation(conversation)

        [start_cmd] = self.get_api_commands_sent()
        self.assertEqual(start_cmd, VumiApiCommand.command(
                '%s_application' % (conversation.conversation_type,), 'start',
                user_account_key=conversation.user_account.key,
                conversation_key=conversation.key))

    def test_show(self):
        """
        Test showing the conversation
        """
        response = self.client.get(self.get_view_url('show'))
        conversation = response.context[0].get('conversation')
        self.assertEqual(conversation.name, self.TEST_CONVERSATION_NAME)
        self.assertContains(response, 'Send Bulk Message')
        self.assertContains(response, self.get_action_view_url('bulk_send'))

    @skip("The new views don't have this.")
    def test_show_cached_message_pagination(self):
        # Create 21 inbound & 21 outbound messages, since we have
        # 20 messages per page it should give us 2 pages
        self.put_sample_messages_in_conversation(self.user_api,
                                                 self.conv_key, 21)
        response = self.client.get(self.get_view_url('show'))

        # Check pagination
        # We should have 60 references to a contact, which by default display
        # the from_addr if a contact cannot be found. (each block as 3
        # references, one in the table listing, 2 in the reply-to modal div)
        self.assertContains(response, 'from-', 60)
        # We should have 2 links to page to, one for the actual page link
        # and one for the 'Next' page link
        self.assertContains(response, '&amp;p=2', 2)
        # There should only be 1 link to the current page
        self.assertContains(response, '&amp;p=1', 1)
        # There should not be a link to the previous page since we are not
        # the first page.
        self.assertContains(response, '&amp;p=0', 0)

    @skip("The new views don't have this.")
    def test_show_cached_message_overview(self):
        self.put_sample_messages_in_conversation(self.user_api,
                                                 self.conv_key, 10)
        response = self.client.get(self.get_view_url('show'))
        self.assertContains(response,
            '10 sent for delivery to the networks.')
        self.assertContains(response,
            '10 accepted for delivery by the networks.')
        self.assertContains(response, '10 delivered.')

    @skip("The new views don't have this.")
    @patch('go.base.message_store_client.MatchResult')
    @patch('go.base.message_store_client.Client')
    def test_message_search(self, Client, MatchResult):
        fake_client = FakeMessageStoreClient()
        fake_result = FakeMatchResult()
        Client.return_value = fake_client
        MatchResult.return_value = fake_result

        response = self.client.get(self.get_view_url('show'), {
            'q': 'hello world 1',
        })

        template_names = [t.name for t in response.templates]
        self.assertTrue(
            'generic/includes/message-load-results.html' in template_names)
        self.assertEqual(response.context['token'], fake_client.token)

    @skip("The new views don't have this.")
    @patch('go.base.message_store_client.MatchResult')
    @patch('go.base.message_store_client.Client')
    def test_message_results(self, Client, MatchResult):
        fake_client = FakeMessageStoreClient()
        fake_result = FakeMatchResult(tries=2,
            results=[self.mkmsg_out() for i in range(10)])
        Client.return_value = fake_client
        MatchResult.return_value = fake_result

        fetch_results_url = self.get_view_url('message_search_result')
        fetch_results_params = {
            'q': 'hello world 1',
            'batch_id': 'batch-id',
            'direction': 'inbound',
            'token': fake_client.token,
            'delay': 100,
        }

        response1 = self.client.get(fetch_results_url, fetch_results_params)
        response2 = self.client.get(fetch_results_url, fetch_results_params)

        # First time it should still show the loading page
        self.assertTrue('generic/includes/message-load-results.html' in
                        [t.name for t in response1.templates])
        self.assertEqual(response1.context['delay'], 1.1 * 100)
        # Second time it should still render the messages
        self.assertTrue('generic/includes/message-list.html' in
                        [t.name for t in response2.templates])
        self.assertEqual(response1.context['token'], fake_client.token)
        # Second time we should list the matching messages
        self.assertEqual(response2.context['token'], fake_client.token)
        self.assertEqual(
            len(response2.context['message_page'].object_list), 10)

    def test_aggregates(self):
        self.put_sample_messages_in_conversation(
            self.user_api, self.conv_key, 10, start_date=date(2012, 1, 1),
            time_multiplier=12)
        response = self.client.get(self.get_view_url('aggregates'),
                                   {'direction': 'inbound'})
        self.assertEqual(response.content, '\r\n'.join([
            '2011-12-28,2',
            '2011-12-29,2',
            '2011-12-30,2',
            '2011-12-31,2',
            '2012-01-01,2',
            '',  # csv ends with a blank line
            ]))

    def test_export_messages(self):
        self.put_sample_messages_in_conversation(
            self.user_api, self.conv_key, 10, start_date=date(2012, 1, 1),
            time_multiplier=12)
        response = self.client.post(self.get_view_url('show'), {
            '_export_conversation_messages': True,
        })
        self.assertRedirects(response, self.get_view_url('show'))
        [email] = mail.outbox
        self.assertEqual(email.recipients(), [self.user.email])
        self.assertTrue(self.conversation.name in email.subject)
        self.assertTrue(self.conversation.name in email.body)
        [(file_name, content, mime_type)] = email.attachments
        self.assertEqual(file_name, 'messages-export.zip')
        # 1 header, 10 sent, 10 received, 1 trailing newline == 22
        self.assertEqual(22, len(content.split('\n')))
        self.assertEqual(mime_type, 'application/zip')

    def test_action_bulk_send_view(self):
        response = self.client.get(self.get_action_view_url('bulk_send'))
        conversation = response.context[0].get('conversation')
        self.assertEqual(conversation.name, self.TEST_CONVERSATION_NAME)
        self.assertEqual([], self.get_api_commands_sent())
        self.assertContains(response, 'name="message"')
        self.assertContains(response, '<h1>Send Bulk Message</h1>')

    def test_action_bulk_send_dedupe(self):
        # Start the conversation
        self.client.post(self.get_view_url('start'))
        self.assertEqual(1, len(self.get_api_commands_sent()))
        response = self.client.post(
            self.get_action_view_url('bulk_send'),
            {'message': 'I am ham, not spam.', 'dedupe': True})
        self.assertRedirects(response, self.get_view_url('show'))
        [bulk_send_cmd] = self.get_api_commands_sent()
        conversation = self.user_api.get_wrapped_conversation(self.conv_key)
        self.assertEqual(bulk_send_cmd, VumiApiCommand.command(
            '%s_application' % (conversation.conversation_type,),
            'bulk_send',
            user_account_key=conversation.user_account.key,
            conversation_key=conversation.key,
            batch_id=conversation.get_batches()[0].key, msg_options={},
            content='I am ham, not spam.', dedupe=True))

    def test_action_bulk_send_no_dedupe(self):
        # Start the conversation
        self.client.post(self.get_view_url('start'))
        self.assertEqual(1, len(self.get_api_commands_sent()))
        response = self.client.post(
            self.get_action_view_url('bulk_send'),
            {'message': 'I am ham, not spam.', 'dedupe': False})
        self.assertRedirects(response, self.get_view_url('show'))
        [bulk_send_cmd] = self.get_api_commands_sent()
        conversation = self.user_api.get_wrapped_conversation(self.conv_key)
        self.assertEqual(bulk_send_cmd, VumiApiCommand.command(
            '%s_application' % (conversation.conversation_type,),
            'bulk_send',
            user_account_key=conversation.user_account.key,
            conversation_key=conversation.key,
            batch_id=conversation.get_batches()[0].key, msg_options={},
            content='I am ham, not spam.', dedupe=False))

    @skip("The new views don't handle this kind of thing very well yet.")
    def test_action_bulk_send_fails(self):
        """
        Test failure to send messages
        """
        self.acquire_all_longcode_tags()
        response = self.client.post(self.get_view_url('start'), follow=True)
        self.assertRedirects(response, self.get_view_url('start'))
        [] = self.get_api_commands_sent()
        [msg] = response.context['messages']
        self.assertEqual(str(msg), "No spare messaging tags.")

    def test_action_bulk_send_confirm(self):
        """
        Test action with confirmation required
        """
        # TODO: Break this test into smaller bits and move them to a more
        #       appropriate module.
        profile = self.user.get_profile()
        account = profile.get_user_account()
        account.msisdn = u'+27761234567'
        account.confirm_start_conversation = True
        account.save()

        # Start the conversation
        self.client.post(self.get_view_url('start'))
        self.assertEqual(1, len(self.get_api_commands_sent()))

        # POST the action with a mock token manager
        with patch.object(TokenManager, 'generate_token') as mock_method:
            mock_method.return_value = ('abcdef', '123456')
            response = self.client.post(
                self.get_action_view_url('bulk_send'),
                {'message': 'I am ham, not spam.', 'dedupe': True})
        self.assertRedirects(response, self.get_view_url('show'))

        # Check that we get a confirmation message
        [token_send_cmd] = self.get_api_commands_sent()
        conversation = self.user_api.get_wrapped_conversation(self.conv_key)
        self.assertEqual(
            VumiApiCommand.command(
                '%s_application' % (conversation.conversation_type,),
                'send_message',
                user_account_key=conversation.user_account.key,
                conversation_key=conversation.key,
                command_data=dict(
                    batch_id=conversation.get_batches()[0].key,
                    to_addr=u'+27761234567', msg_options={
                        'helper_metadata': {'go': {'sensitive': True}},
                    },
                    content=RegexMatcher(r'Please visit http://[^/]+/t/abcdef/'
                                         r' to start your conversation.')),
            ),
            token_send_cmd)

        # GET the token URL
        confirm_response = self.client.get(
            reverse('token', kwargs={'token': 'abcdef'}))
        self.assertRedirects(
            confirm_response,
            self.get_view_url('confirm') + '?token=6-abcdef123456')

        # POST the full token to the confirmation URL
        final_response = self.client.post(self.get_view_url('confirm'), {
            'token': '6-abcdef123456',
        })
        self.assertRedirects(final_response, self.get_view_url('show'))

        [bulk_send_cmd] = self.get_api_commands_sent()
        self.assertEqual(bulk_send_cmd, VumiApiCommand.command(
            '%s_application' % (conversation.conversation_type,),
            'bulk_send',
            user_account_key=conversation.user_account.key,
            conversation_key=conversation.key,
            batch_id=conversation.get_batches()[0].key, msg_options={},
            content='I am ham, not spam.', dedupe=True))


class SendOneOffReplyTestCase(DjangoGoApplicationTestCase):

    def setUp(self):
        super(SendOneOffReplyTestCase, self).setUp()
        self.setup_riak_fixtures()
        self.client = Client()
        self.client.login(username='username', password='password')

    def get_view_url(self, view, conv_key=None):
        if conv_key is None:
            conv_key = self.conv_key
        view_def = get_conversation_view_definition(
            self.TEST_CONVERSATION_TYPE)
        return view_def.get_view_url(view, conversation_key=conv_key)

    def get_wrapped_conv(self):
        conv = self.conv_store.get_conversation_by_key(self.conv_key)
        return self.user_api.wrap_conversation(conv)

    @skip("The new views don't have this.")
    def test_actions_on_inbound_only(self):
        messages = self.put_sample_messages_in_conversation(self.user_api,
                                                            self.conv_key, 1)
        [msg_in, msg_out, ack, dr] = messages[0]

        response = self.client.get(self.get_view_url('show'),
                                   {'direction': 'inbound'})
        self.assertContains(response, 'Reply')
        self.assertContains(response, 'href="#reply-%s"' % (
            msg_in['message_id'],))

        response = self.client.get(self.get_view_url('show'),
                                   {'direction': 'outbound'})
        self.assertNotContains(response, 'Reply')

    def test_send_one_off_reply(self):
        self.put_sample_messages_in_conversation(self.user_api,
                                                 self.conv_key, 1)
        conversation = self.get_wrapped_conv()
        [msg] = conversation.received_messages()
        response = self.client.post(self.get_view_url('show'), {
            'in_reply_to': msg['message_id'],
            'content': 'foo',
            'to_addr': 'should be ignored',
            '_send_one_off_reply': True,
        })
        self.assertRedirects(response, self.get_view_url('show'))

        [start_cmd, hack_cmd, reply_to_cmd] = self.get_api_commands_sent()
        [tag] = conversation.get_tags()
        msg_options = conversation.make_message_options(tag)
        msg_options['in_reply_to'] = msg['message_id']
        self.assertEqual(reply_to_cmd['worker_name'],
                            'bulk_message_application')
        self.assertEqual(reply_to_cmd['command'], 'send_message')
        self.assertEqual(reply_to_cmd['args'],
                         [self.conversation.user_account.key,
                          self.conversation.key])
        self.assertEqual(reply_to_cmd['kwargs']['command_data'], {
            'batch_id': conversation.get_latest_batch_key(),
            'conversation_key': conversation.key,
            'content': 'foo',
            'to_addr': msg['from_addr'],
            'msg_options': msg_options,
            })
