from go.vumitools.tests.utils import VumiApiCommand
from go.apps.tests.base import DjangoGoApplicationTestCase
from go.apps.surveys.view_definition import get_poll_config


class SurveyTestCase(DjangoGoApplicationTestCase):

    TEST_CONVERSATION_TYPE = u'survey'
    TEST_CHANNEL_METADATA = {
        "supports": {
            "generic_sends": True,
        },
    }

    def setUp(self):
        super(SurveyTestCase, self).setUp()
        self.patch_settings(
            VXPOLLS_REDIS_CONFIG=self._persist_config['redis_manager'])

    def create_poll(self, conversation, **kwargs):
        poll_id = 'poll-%s' % (conversation.key,)
        pm, config = get_poll_config(poll_id)
        config.update(kwargs)
        return pm, pm.register(poll_id, config)

    def test_action_send_survey_get(self):
        self.setup_conversation(started=True, with_group=True,
                                with_channel=True)
        response = self.client.get(self.get_action_view_url('send_survey'))
        conversation = response.context[0].get('conversation')
        self.assertEqual(conversation.name, self.TEST_CONVERSATION_NAME)
        self.assertEqual([], self.get_api_commands_sent())

    def test_action_send_survey_post(self):
        self.setup_conversation(started=True, with_group=True,
                                with_channel=True)
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
            batch_id=conversation.batch.key, msg_options={},
            delivery_class=conversation.delivery_class))

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
        self.setup_conversation(started=True, with_group=True,
                                with_channel=True)
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
