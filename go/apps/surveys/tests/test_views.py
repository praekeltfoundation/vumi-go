from datetime import date
from zipfile import ZipFile
from StringIO import StringIO

from django.core import mail
from django.utils.unittest import skip

from go.vumitools.tests.utils import VumiApiCommand
from go.apps.tests.base import DjangoGoApplicationTestCase
from go.apps.surveys.view_definition import get_poll_config
from go.base.tests.utils import FakeMessageStoreClient, FakeMatchResult

from mock import patch


class SurveyTestCase(DjangoGoApplicationTestCase):

    TEST_CONVERSATION_TYPE = u'survey'

    def setUp(self):
        super(SurveyTestCase, self).setUp()
        self.patch_settings(
            VXPOLLS_REDIS_CONFIG=self._persist_config['redis_manager'])

    def create_poll(self, conversation, **kwargs):
        poll_id = 'poll-%s' % (conversation.key,)
        pm, config = get_poll_config(poll_id)
        config.update(kwargs)
        return pm, pm.register(poll_id, config)

    def attach_channel(self):
        self.declare_tags("pool", 1, {
            "supports": {"generic_sends": True}})
        self.add_channel_to_conversation(
            self.conversation, ["pool", "default1"])

    def test_new_conversation(self):
        self.add_app_permission(u'go.apps.surveys')
        self.assertEqual(len(self.conv_store.list_conversations()), 0)
        response = self.post_new_conversation()
        self.assertEqual(len(self.conv_store.list_conversations()), 1)
        conv = self.get_latest_conversation()
        self.assertRedirects(response, self.get_view_url('show', conv.key))

    def test_stop(self):
        self.setup_conversation(started=True)
        response = self.client.post(self.get_view_url('stop'), follow=True)
        self.assertRedirects(response, self.get_view_url('show'))
        [msg] = response.context['messages']
        self.assertEqual(str(msg), "Conversation stopped")
        conversation = self.get_wrapped_conv()
        self.assertTrue(conversation.stopping())

    def test_action_send_survey_get(self):
        self.setup_conversation(started=True, with_group=True)
        self.attach_channel()
        response = self.client.get(self.get_action_view_url('send_survey'))
        conversation = response.context[0].get('conversation')
        self.assertEqual(conversation.name, self.TEST_CONVERSATION_NAME)
        self.assertEqual([], self.get_api_commands_sent())

    def test_action_send_survey_post(self):
        self.setup_conversation(started=True, with_group=True)
        response = self.client.post(
            self.get_action_view_url('send_survey'), {}, follow=True)
        self.assertRedirects(response, self.get_view_url('show'))
        [send_survey_cmd] = self.get_api_commands_sent()
        conversation = self.get_wrapped_conv()
        self.assertEqual(send_survey_cmd, VumiApiCommand.command(
            '%s_application' % (conversation.conversation_type,),
            'send_survey',
            user_account_key=conversation.user_account.key,
            conversation_key=conversation.key,
            batch_id=conversation.get_batches()[0].key, msg_options={},
            delivery_class=conversation.delivery_class,
            is_client_initiated=False))

    def test_action_send_survey_no_group(self):
        self.setup_conversation(started=True)
        response = self.client.post(
            self.get_action_view_url('send_survey'), {}, follow=True)
        self.assertRedirects(response, self.get_view_url('show'))
        [msg] = response.context['messages']
        self.assertEqual(
            str(msg), "Action disabled: This action needs a contact group.")
        self.assertEqual([], self.get_api_commands_sent())

    def test_action_send_survey_not_running(self):
        self.setup_conversation(with_group=True)
        response = self.client.post(
            self.get_action_view_url('send_survey'), {}, follow=True)
        self.assertRedirects(response, self.get_view_url('show'))
        [msg] = response.context['messages']
        self.assertEqual(
            str(msg),
            "Action disabled: This action needs a running conversation.")
        self.assertEqual([], self.get_api_commands_sent())

    def test_action_send_survey_no_channel(self):
        self.setup_conversation(started=True, with_group=True)
        response = self.client.post(
            self.get_action_view_url('send_survey'), {}, follow=True)
        self.assertRedirects(response, self.get_view_url('show'))
        [msg] = response.context['messages']
        self.assertEqual(
            str(msg),
            "Action disabled: This action needs channels capable"
            " of sending messages attached to this conversation.")
        self.assertEqual([], self.get_api_commands_sent())

    @skip("The new views don't have this yet.")
    def test_group_selection(self):
        """Select an existing group and use that as the group for the
        conversation"""
        conversation = self.get_wrapped_conv()
        self.assertFalse(conversation.is_client_initiated())
        response = self.client.post(self.get_view_url('people'), {
            'groups': [grp.key for grp in self.contact_store.list_groups()]})
        self.assertRedirects(response, self.get_view_url('start'))

    def test_start(self):
        """
        Test the start conversation view
        """
        self.setup_conversation()
        response = self.client.post(self.get_view_url('start'))
        self.assertRedirects(response, self.get_view_url('show'))

        conversation = self.get_wrapped_conv()
        [start_cmd] = self.get_api_commands_sent()
        [batch] = conversation.get_batches()
        self.assertEqual([], list(batch.tags))

        self.assertEqual(start_cmd, VumiApiCommand.command(
            '%s_application' % (conversation.conversation_type,), 'start',
            user_account_key=conversation.user_account.key,
            conversation_key=conversation.key))

    def test_start_with_group(self):
        """
        Test the start conversation view
        """
        self.setup_conversation(with_group=True, with_contact=True)
        response = self.client.post(self.get_view_url('start'))
        self.assertRedirects(response, self.get_view_url('show'))

        conversation = self.get_wrapped_conv()
        [start_cmd] = self.get_api_commands_sent()
        [batch] = conversation.get_batches()
        self.assertEqual([], list(batch.tags))
        [contact] = self.get_contacts_for_conversation(conversation)

        self.assertEqual(start_cmd, VumiApiCommand.command(
            '%s_application' % (conversation.conversation_type,), 'start',
            user_account_key=conversation.user_account.key,
            conversation_key=conversation.key))

    def test_show_stopped(self):
        """
        Test showing the conversation
        """
        self.setup_conversation()
        response = self.client.get(self.get_view_url('show'))
        conversation = response.context[0].get('conversation')
        self.assertEqual(conversation.name, 'Test Conversation')
        self.assertNotContains(
            response, self.get_action_view_url('send_survey'))

    def test_show_running(self):
        """
        Test showing the conversation
        """
        self.setup_conversation(started=True, with_group=True)
        response = self.client.get(self.get_view_url('show'))
        conversation = response.context[0].get('conversation')
        self.assertEqual(conversation.name, 'Test Conversation')
        self.assertContains(response, self.get_action_view_url('send_survey'))

    def test_edit(self):
        self.setup_conversation()
        response = self.client.post(self.get_view_url('edit'), {
            'questions-TOTAL_FORMS': 1,
            'questions-INITIAL_FORMS': 0,
            'questions-MAX_NUM_FORMS': '',
            'questions-0-copy': 'What is your favorite music?',
            'questions-0-label': 'favorite music',
            'questions-0-valid_responses': 'rock, jazz, techno',
            'completed_response-TOTAL_FORMS': 0,
            'completed_response-INITIAL_FORMS': 0,
            'completed_response-MAX_NUM_FORMS': '',
        })
        self.assertRedirects(response, self.get_view_url('show'))
        poll_id = 'poll-%s' % (self.conv_key,)
        pm, config = get_poll_config(poll_id)
        [question] = config['questions']
        self.assertEqual(question['copy'], 'What is your favorite music?')
        self.assertEqual(question['valid_responses'], [
            'rock', 'jazz', 'techno'])
        self.assertEqual(question['label'], 'favorite music')

    def test_edit_continue_editing(self):
        self.setup_conversation()
        response = self.client.post(self.get_view_url('edit'), {
            'questions-TOTAL_FORMS': 1,
            'questions-INITIAL_FORMS': 0,
            'questions-MAX_NUM_FORMS': '',
            'questions-0-copy': 'What is your favorite music?',
            'questions-0-label': 'favorite music',
            'questions-0-valid_responses': 'rock, jazz, techno',
            'completed_response-TOTAL_FORMS': 0,
            'completed_response-INITIAL_FORMS': 0,
            'completed_response-MAX_NUM_FORMS': '',
            '_save_contents': 1
        })
        self.assertRedirects(response, self.get_view_url('edit'))
        poll_id = 'poll-%s' % (self.conv_key,)
        pm, config = get_poll_config(poll_id)
        [question] = config['questions']
        self.assertEqual(question['copy'], 'What is your favorite music?')
        self.assertEqual(question['valid_responses'], [
            'rock', 'jazz', 'techno'])
        self.assertEqual(question['label'], 'favorite music')

    def test_export_user_data(self):
        self.setup_conversation()
        pm, poll = self.create_poll(self.conversation, questions=[{
                'copy': 'question-1',
                'label': 'label-1',
            }, {
                'copy': 'question-2',
                'label': 'label-2',
            }])

        participant = pm.get_participant(poll.poll_id, 'user-1')
        participant.has_unanswered_question = True
        participant.set_last_question_index(0)
        poll.submit_answer(participant, 'answer 1')
        participant.set_last_question_index(1)
        poll.submit_answer(participant, 'answer 2')

        response = self.client.get(self.get_view_url('user_data'))
        self.assertEqual(response['Content-Type'], 'application/csv')
        lines = response.content.split('\r\n')
        self.assertEqual(lines[0], 'user_id,user_timestamp,label-1,label-2')
        self.assertTrue(lines[1].startswith('user-1'))
        self.assertTrue(lines[1].endswith(',answer 1,answer 2'))

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
        response = self.client.post(self.get_view_url('show'), {
            '_export_conversation_messages': True,
        })
        self.assertRedirects(response, self.get_view_url('show'))
        [email] = mail.outbox
        self.assertEqual(email.recipients(), [self.django_user.email])
        self.assertTrue(self.conversation.name in email.subject)
        self.assertTrue(self.conversation.name in email.body)
        [(file_name, contents, mime_type)] = email.attachments
        self.assertEqual(file_name, 'messages-export.zip')

        zipfile = ZipFile(StringIO(contents), 'r')
        csv_contents = zipfile.open('messages-export.csv', 'r').read()

        # 1 header, 5 sent, 5 received, 1 trailing newline == 12
        self.assertEqual(12, len(csv_contents.split('\n')))
        self.assertEqual(mime_type, 'application/zip')

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
        self.assertTrue('generic/includes/message-load-results.html' in
                        template_names)
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

        fetch_results_params = {
            'q': 'hello world 1',
            'batch_id': 'batch-id',
            'direction': 'inbound',
            'token': fake_client.token,
            'delay': 100,
        }

        response1 = self.client.get(self.get_view_url('message_search_result'),
                                    fetch_results_params)
        response2 = self.client.get(self.get_view_url('message_search_result'),
                                    fetch_results_params)

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
        self.assertEqual(len(response2.context['message_page'].object_list),
            10)

    def test_send_one_off_reply(self):
        self.setup_conversation(started=True)
        self.add_messages_to_conv(1)
        conversation = self.get_wrapped_conv()
        [msg] = conversation.received_messages()
        response = self.client.post(self.get_view_url('show'), {
            'in_reply_to': msg['message_id'],
            'content': 'foo',
            'to_addr': 'should be ignored',
            '_send_one_off_reply': True,
        })
        self.assertRedirects(response, self.get_view_url('show'))

        [reply_to_cmd] = self.get_api_commands_sent()
        self.assertEqual(reply_to_cmd['worker_name'],
                         'survey_application')
        self.assertEqual(reply_to_cmd['command'], 'send_message')
        self.assertEqual(reply_to_cmd['kwargs']['command_data'], {
            'batch_id': conversation.get_latest_batch_key(),
            'conversation_key': conversation.key,
            'content': 'foo',
            'to_addr': msg['from_addr'],
            'msg_options': {'in_reply_to': msg['message_id']},
        })
