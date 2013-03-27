from datetime import date

from django.test.client import Client
from django.core.urlresolvers import reverse
from django.core import mail

from go.vumitools.tests.utils import VumiApiCommand
from go.apps.tests.base import DjangoGoApplicationTestCase
from go.apps.surveys.views import get_poll_config
from go.base.tests.utils import FakeMessageStoreClient, FakeMatchResult

from mock import patch


class SurveyTestCase(DjangoGoApplicationTestCase):

    TEST_CONVERSATION_TYPE = u'survey'

    def setUp(self):
        super(SurveyTestCase, self).setUp()
        self.setup_riak_fixtures()
        self.client = Client()
        self.client.login(username='username', password='password')
        self.patch_settings(VXPOLLS_REDIS_CONFIG={'FAKE_REDIS': 'sure'})

    def get_wrapped_conv(self):
        conv = self.conv_store.get_conversation_by_key(self.conv_key)
        return self.user_api.wrap_conversation(conv)

    def create_poll(self, conversation, **kwargs):
        poll_id = 'poll-%s' % (conversation.key,)
        pm, config = get_poll_config(poll_id)
        config.update(kwargs)
        return pm, pm.register(poll_id, config)

    def run_new_conversation(self, selected_option, pool, tag):
        # render the form
        self.assertEqual(len(self.conv_store.list_conversations()), 1)
        response = self.client.get(reverse('survey:new'))
        self.assertEqual(response.status_code, 200)
        # post the form
        response = self.client.post(reverse('survey:new'), {
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
        self.assertRedirects(response, reverse('survey:contents', kwargs={
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

        self.api.tpm.set_metadata("pool1", {
            "delivery_class": "sms",
            "server_initiated": True,
            })

        self.api.tpm.set_metadata("pool2", {
            "delivery_class": "ussd",
            "client_initiated": True,
            })

        def get_people_page(tag_pool):
            conversation = self.get_wrapped_conv()
            conversation.c.delivery_tag_pool = tag_pool
            conversation.save()
            return self.client.get(reverse('survey:people', kwargs={
                'conversation_key': conversation.key,
                }))

        self.assertContains(get_people_page(u'pool1'), 'Survey Recipients')
        self.assertNotContains(get_people_page(u'pool2'), 'Survey Recipients')

    def test_group_selection(self):
        """Select an existing group and use that as the group for the
        conversation"""
        conversation = self.get_wrapped_conv()
        self.assertFalse(conversation.is_client_initiated())
        response = self.client.post(reverse('survey:people',
            kwargs={'conversation_key': conversation.key}), {'groups': [
                    grp.key for grp in self.contact_store.list_groups()]})
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

        self.assertEqual(cmd, VumiApiCommand.command(
            '%s_application' % (conversation.conversation_type,), 'start',
            conversation_type=conversation.conversation_type,
            conversation_key=conversation.key,
            is_client_initiated=conversation.is_client_initiated(),
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
        self.assertEqual(conversation.name, 'Test Conversation')

    def test_edit(self):
        survey_url = reverse('survey:edit', kwargs={
            'conversation_key': self.conv_key,
            })
        show_url = reverse('survey:show', kwargs={
            'conversation_key': self.conv_key,
            })
        response = self.client.post(survey_url, {
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
        self.assertRedirects(response, show_url)
        poll_id = 'poll-%s' % (self.conv_key,)
        pm, config = get_poll_config(poll_id)
        [question] = config['questions']
        self.assertEqual(question['copy'], 'What is your favorite music?')
        self.assertEqual(question['valid_responses'], [
            'rock', 'jazz', 'techno'])
        self.assertEqual(question['label'], 'favorite music')

    def test_edit_continue_editing(self):
        survey_url = reverse('survey:edit', kwargs={
            'conversation_key': self.conv_key,
        })
        response = self.client.post(survey_url, {
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
        self.assertRedirects(response, survey_url)
        poll_id = 'poll-%s' % (self.conv_key,)
        pm, config = get_poll_config(poll_id)
        [question] = config['questions']
        self.assertEqual(question['copy'], 'What is your favorite music?')
        self.assertEqual(question['valid_responses'], [
            'rock', 'jazz', 'techno'])
        self.assertEqual(question['label'], 'favorite music')

    def test_export_user_data(self):
        survey_url = reverse('survey:user_data', kwargs={
            'conversation_key': self.conv_key,
        })
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

        response = self.client.get(survey_url)
        self.assertEqual(response['Content-Type'], 'application/csv')
        lines = response.content.split('\r\n')
        self.assertEqual(lines[0], 'user_id,user_timestamp,label-1,label-2')
        self.assertTrue(lines[1].startswith('user-1'))
        self.assertTrue(lines[1].endswith(',answer 1,answer 2'))

    def test_aggregates(self):
        self.put_sample_messages_in_conversation(self.user_api,
            self.conv_key, 10, start_timestamp=date(2012, 1, 1),
            time_multiplier=12)
        response = self.client.get(reverse('survey:aggregates', kwargs={
            'conversation_key': self.conv_key
            }), {'direction': 'inbound'})
        self.assertEqual(response.content, '\r\n'.join([
            '2011-12-28,2',
            '2011-12-29,2',
            '2011-12-30,2',
            '2011-12-31,2',
            '2012-01-01,2',
            '',  # csv ends with a blank line
            ]))

    def test_export_messages(self):
        self.put_sample_messages_in_conversation(self.user_api,
            self.conv_key, 10, start_timestamp=date(2012, 1, 1),
            time_multiplier=12)
        conv_url = reverse('survey:show', kwargs={
            'conversation_key': self.conv_key,
            })
        response = self.client.post(conv_url, {
            '_export_conversation_messages': True,
            })
        self.assertRedirects(response, conv_url)
        [email] = mail.outbox
        self.assertEqual(email.recipients(), [self.user.email])
        self.assertTrue(self.conversation.name in email.subject)
        self.assertTrue(self.conversation.name in email.body)
        [(file_name, content, mime_type)] = email.attachments
        self.assertEqual(file_name, 'messages-export.csv')
        # 1 header, 10 sent, 10 received, 1 trailing newline == 22
        self.assertEqual(22, len(content.split('\n')))
        self.assertEqual(mime_type, 'text/csv')

    @patch('go.base.message_store_client.MatchResult')
    @patch('go.base.message_store_client.Client')
    def test_message_search(self, Client, MatchResult):
        fake_client = FakeMessageStoreClient()
        fake_result = FakeMatchResult()
        Client.return_value = fake_client
        MatchResult.return_value = fake_result

        response = self.client.get(reverse('survey:show', kwargs={
                'conversation_key': self.conv_key,
            }), {
                'q': 'hello world 1',
            })

        template_names = [t.name for t in response.templates]
        self.assertTrue('generic/includes/message-load-results.html' in
                        template_names)
        self.assertEqual(response.context['token'], fake_client.token)

    @patch('go.base.message_store_client.MatchResult')
    @patch('go.base.message_store_client.Client')
    def test_message_results(self, Client, MatchResult):
        fake_client = FakeMessageStoreClient()
        fake_result = FakeMatchResult(tries=2,
            results=[self.mkmsg_out() for i in range(10)])
        Client.return_value = fake_client
        MatchResult.return_value = fake_result

        fetch_results_url = reverse('survey:message_search_result',
            kwargs={
                'conversation_key': self.conv_key,
            })
        fetch_results_params = {
            'q': 'hello world 1',
            'batch_id': 'batch-id',
            'direction': 'inbound',
            'token': fake_client.token,
            'delay': 100,
        }

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
        self.assertEqual(response1.context['token'], fake_client.token)
        # Second time we should list the matching messages
        self.assertEqual(response2.context['token'], fake_client.token)
        self.assertEqual(len(response2.context['message_page'].object_list),
            10)

    def test_send_one_off_reply(self):
        self.put_sample_messages_in_conversation(self.user_api,
                                                    self.conv_key, 1)
        conversation = self.get_wrapped_conv()
        [msg] = conversation.received_messages()
        response = self.client.post(reverse('survey:show', kwargs={
            'conversation_key': self.conv_key
            }), {
                'in_reply_to': msg['message_id'],
                'content': 'foo',
                'to_addr': 'should be ignored',
                '_send_one_off_reply': True,
            })
        self.assertRedirects(response, reverse('survey:show', kwargs={
            'conversation_key': self.conv_key,
            }))

        [start_cmd, reply_to_cmd] = self.get_api_commands_sent()
        [tag] = conversation.get_tags()
        msg_options = conversation.make_message_options(tag)
        msg_options['in_reply_to'] = msg['message_id']
        self.assertEqual(reply_to_cmd['worker_name'],
                            'survey_application')
        self.assertEqual(reply_to_cmd['command'], 'send_message')
        self.assertEqual(reply_to_cmd['kwargs']['command_data'], {
            'batch_id': conversation.get_latest_batch_key(),
            'conversation_key': conversation.key,
            'content': 'foo',
            'to_addr': msg['from_addr'],
            'msg_options': msg_options,
            })
