from datetime import date
from StringIO import StringIO
from zipfile import ZipFile

from django.core import mail
from django.core.urlresolvers import reverse
from django.utils.unittest import skip

from vumi.tests.utils import RegexMatcher

from go.vumitools.tests.utils import VumiApiCommand
from go.vumitools.token_manager import TokenManager
from go.apps.tests.base import DjangoGoApplicationTestCase
from go.base.tests.utils import FakeMessageStoreClient, FakeMatchResult

from mock import patch


class BulkMessageTestCase(DjangoGoApplicationTestCase):

    TEST_CONVERSATION_TYPE = u'bulk_message'
    TEST_CHANNEL_METADATA = {
        "supports": {
            "generic_sends": True,
        },
    }

    def test_new_conversation(self):
        self.add_app_permission(u'go.apps.bulk_message')
        self.assertEqual(len(self.conv_store.list_conversations()), 0)
        response = self.post_new_conversation()
        self.assertEqual(len(self.conv_store.list_conversations()), 1)
        conv = self.get_latest_conversation()
        self.assertRedirects(response, self.get_view_url('show', conv.key))

    def test_show_stopped(self):
        """
        Test showing the conversation
        """
        self.setup_conversation()
        response = self.client.get(self.get_view_url('show'))
        conversation = response.context[0].get('conversation')
        self.assertEqual(conversation.name, self.TEST_CONVERSATION_NAME)
        self.assertContains(response, 'Write and send bulk message')
        self.assertNotContains(response, self.get_action_view_url('bulk_send'))

    def test_show_running(self):
        """
        Test showing the conversation
        """
        self.setup_conversation(started=True, with_group=True,
                                with_channel=True)
        response = self.client.get(self.get_view_url('show'))
        conversation = response.context[0].get('conversation')
        self.assertEqual(conversation.name, self.TEST_CONVERSATION_NAME)
        self.assertContains(response, 'Write and send bulk message')
        self.assertContains(response, self.get_action_view_url('bulk_send'))

    def test_show_cached_message_pagination(self):
        self.setup_conversation()
        # Create 21 inbound & 21 outbound messages, since we have
        # 20 messages per page it should give us 2 pages
        self.add_messages_to_conv(21)
        response = self.client.get(self.get_view_url('message_list'))

        # Check pagination
        # Ordinarily we'd have 60 references to a contact, which by default
        # display the from_addr if a contact cannot be found. (Each block has 3
        # references, one in the table listing, 2 in the reply-to modal div.)
        # We have no channels connected to this conversation, however, so we
        # only have 20 in this test.
        self.assertContains(response, 'from-', 20)
        # We should have 2 links to page two, one for the actual page link
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
        self.setup_conversation()
        fake_client = FakeMessageStoreClient()
        fake_result = FakeMatchResult()
        Client.return_value = fake_client
        MatchResult.return_value = fake_result

        response = self.client.get(self.get_view_url('message_list'), {
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
        self.setup_conversation()
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
        self.setup_conversation(started=True)
        self.add_messages_to_conv(
            5, start_date=date(2012, 1, 1), time_multiplier=12)
        response = self.client.get(self.get_view_url('aggregates'),
                                   {'direction': 'inbound'})
        self.assertEqual(response.content, '\r\n'.join([
            '2011-12-30,1',
            '2011-12-31,2',
            '2012-01-01,2',
            '',  # csv ends with a blank line
            ]))

    def test_export_messages(self):
        self.setup_conversation(started=True)
        self.add_messages_to_conv(
            5, start_date=date(2012, 1, 1), time_multiplier=12, reply=True)
        response = self.client.post(self.get_view_url('message_list'), {
            '_export_conversation_messages': True,
        })
        self.assertRedirects(response, self.get_view_url('message_list'))
        [email] = mail.outbox
        self.assertEqual(email.recipients(), [self.django_user.email])
        self.assertTrue(self.conversation.name in email.subject)
        self.assertTrue(self.conversation.name in email.body)
        [(file_name, zipcontent, mime_type)] = email.attachments
        self.assertEqual(file_name, 'messages-export.zip')
        zipfile = ZipFile(StringIO(zipcontent), 'r')
        content = zipfile.open('messages-export.csv', 'r').read()
        # 1 header, 5 sent, 5 received, 1 trailing newline == 12
        self.assertEqual(12, len(content.split('\n')))
        self.assertEqual(mime_type, 'application/zip')

    def test_action_bulk_send_view(self):
        self.setup_conversation(started=True, with_group=True,
                                with_channel=True)
        response = self.client.get(self.get_action_view_url('bulk_send'))
        conversation = response.context[0].get('conversation')
        self.assertEqual(conversation.name, self.TEST_CONVERSATION_NAME)
        self.assertEqual([], self.get_api_commands_sent())
        self.assertContains(response, 'name="message"')
        self.assertContains(response, '<h1>Write and send bulk message</h1>')

    def test_action_bulk_send_no_group(self):
        self.setup_conversation(started=True)
        response = self.client.post(
            self.get_action_view_url('bulk_send'),
            {'message': 'I am ham, not spam.', 'dedupe': True},
            follow=True)
        self.assertRedirects(response, self.get_view_url('show'))
        [msg] = response.context['messages']
        self.assertEqual(
            str(msg), "Action disabled: This action needs a contact group.")
        self.assertEqual([], self.get_api_commands_sent())

    def test_action_bulk_send_not_running(self):
        self.setup_conversation(with_group=True)
        response = self.client.post(
            self.get_action_view_url('bulk_send'),
            {'message': 'I am ham, not spam.', 'dedupe': True},
            follow=True)
        self.assertRedirects(response, self.get_view_url('show'))
        [msg] = response.context['messages']
        self.assertEqual(
            str(msg),
            "Action disabled: This action needs a running conversation.")
        self.assertEqual([], self.get_api_commands_sent())

    def test_action_bulk_send_no_channel(self):
        self.setup_conversation(started=True, with_group=True)
        response = self.client.post(
            self.get_action_view_url('bulk_send'),
            {'message': 'I am ham, not spam.', 'dedupe': True},
            follow=True)
        self.assertRedirects(response, self.get_view_url('show'))
        [msg] = response.context['messages']
        self.assertEqual(
            str(msg),
            "Action disabled: This action needs channels capable of sending"
            " messages attached to this conversation.")
        self.assertEqual([], self.get_api_commands_sent())

    def test_action_bulk_send_dedupe(self):
        self.setup_conversation(started=True, with_group=True,
                                with_channel=True)
        response = self.client.post(
            self.get_action_view_url('bulk_send'),
            {'message': 'I am ham, not spam.', 'dedupe': True})
        self.assertRedirects(response, self.get_view_url('show'))
        [bulk_send_cmd] = self.get_api_commands_sent()
        conversation = self.get_wrapped_conv()
        self.assertEqual(bulk_send_cmd, VumiApiCommand.command(
            '%s_application' % (conversation.conversation_type,),
            'bulk_send',
            user_account_key=conversation.user_account.key,
            conversation_key=conversation.key,
            batch_id=conversation.batch.key, msg_options={},
            delivery_class=conversation.delivery_class,
            content='I am ham, not spam.', dedupe=True))

    def test_action_bulk_send_no_dedupe(self):
        self.setup_conversation(started=True, with_group=True,
                                with_channel=True)
        response = self.client.post(
            self.get_action_view_url('bulk_send'),
            {'message': 'I am ham, not spam.', 'dedupe': False})
        self.assertRedirects(response, self.get_view_url('show'))
        [bulk_send_cmd] = self.get_api_commands_sent()
        conversation = self.get_wrapped_conv()
        self.assertEqual(bulk_send_cmd, VumiApiCommand.command(
            '%s_application' % (conversation.conversation_type,),
            'bulk_send',
            user_account_key=conversation.user_account.key,
            conversation_key=conversation.key,
            batch_id=conversation.batch.key, msg_options={},
            delivery_class=conversation.delivery_class,
            content='I am ham, not spam.', dedupe=False))

    def test_action_bulk_send_confirm(self):
        """
        Test action with confirmation required
        """
        # TODO: Break this test into smaller bits and move them to a more
        #       appropriate module.
        user_account = self.user_api.get_user_account()
        user_account.msisdn = u'+27761234567'
        user_account.confirm_start_conversation = True
        user_account.save()

        # Start the conversation
        self.setup_conversation(started=True, with_group=True,
                                with_channel=True)

        # POST the action with a mock token manager
        with patch.object(TokenManager, 'generate_token') as mock_method:
            mock_method.return_value = ('abcdef', '123456')
            response = self.client.post(
                self.get_action_view_url('bulk_send'),
                {'message': 'I am ham, not spam.', 'dedupe': True})
        self.assertRedirects(response, self.get_view_url('show'))

        # Check that we get a confirmation message
        [token_send_cmd] = self.get_api_commands_sent()
        conversation = self.get_wrapped_conv()
        self.assertEqual(
            VumiApiCommand.command(
                '%s_application' % (conversation.conversation_type,),
                'send_message',
                user_account_key=conversation.user_account.key,
                conversation_key=conversation.key,
                command_data=dict(
                    batch_id=conversation.batch.key,
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
            batch_id=conversation.batch.key, msg_options={},
            delivery_class=conversation.delivery_class,
            content='I am ham, not spam.', dedupe=True))

    @patch('go.vumitools.conversation.utils.ConversationWrapper.'
           'has_channel_supporting_generic_sends')
    def test_actions_on_inbound_only(self, hcsgs):
        hcsgs.return_value = True
        self.setup_conversation()
        messages = self.add_messages_to_conv(1, reply=True)
        [msg_in, msg_out] = messages[0]

        response = self.client.get(
            self.get_view_url('message_list'), {'direction': 'inbound'})
        self.assertContains(response, 'Reply')
        self.assertContains(response, 'href="#reply-%s"' % (
            msg_in['message_id'],))

        response = self.client.get(
            self.get_view_url('message_list'), {'direction': 'outbound'})
        self.assertNotContains(response, 'Reply')

    def test_no_actions_on_inbound_with_no_generic_send_channels(self):
        # We have no routing hooked up and hence no channels supporting generic
        # sends.
        self.setup_conversation()
        messages = self.add_messages_to_conv(1, reply=True)
        [msg_in, msg_out] = messages[0]

        response = self.client.get(
            self.get_view_url('message_list'), {'direction': 'inbound'})
        self.assertNotContains(response, 'Reply')

    def test_send_one_off_reply(self):
        self.setup_conversation(started=True, with_group=True)
        self.add_messages_to_conv(1)
        conversation = self.get_wrapped_conv()
        [msg] = conversation.received_messages()
        response = self.client.post(self.get_view_url('message_list'), {
            'in_reply_to': msg['message_id'],
            'content': 'foo',
            'to_addr': 'should be ignored',
            '_send_one_off_reply': True,
        })
        self.assertRedirects(response, self.get_view_url('message_list'))

        [reply_to_cmd] = self.get_api_commands_sent()
        self.assertEqual(reply_to_cmd['worker_name'],
                            'bulk_message_application')
        self.assertEqual(reply_to_cmd['command'], 'send_message')
        self.assertEqual(reply_to_cmd['args'],
                         [self.conversation.user_account.key,
                          self.conversation.key])
        self.assertEqual(reply_to_cmd['kwargs']['command_data'], {
            'batch_id': conversation.batch.key,
            'conversation_key': conversation.key,
            'content': 'foo',
            'to_addr': msg['from_addr'],
            'msg_options': {'in_reply_to': msg['message_id']},
        })
