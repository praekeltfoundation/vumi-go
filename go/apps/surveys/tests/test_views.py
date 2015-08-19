from StringIO import StringIO
from zipfile import ZipFile

from go.vumitools.api import VumiApiCommand
from go.vumitools.tests.helpers import djangotest_imports

with djangotest_imports(globals()):
    from django.core import mail

    from go.apps.surveys.view_definition import get_poll_config
    from go.apps.tests.view_helpers import AppViewsHelper
    from go.base.tests.helpers import GoDjangoTestCase


class TestSurveysViews(GoDjangoTestCase):

    def setUp(self):
        self.app_helper = self.add_helper(AppViewsHelper(u'survey'))
        self.client = self.app_helper.get_client()
        redis_config = self.app_helper.mk_config({})['redis_manager']
        self.app_helper.patch_settings(VXPOLLS_REDIS_CONFIG=redis_config)

    def create_poll(self, conversation, **kwargs):
        poll_id = 'poll-%s' % (conversation.key,)
        pm, config = get_poll_config(poll_id)
        config.update(kwargs)
        return pm, pm.register(poll_id, config)

    def test_action_send_survey_get(self):
        group = self.app_helper.create_group_with_contacts(u'test_group', 0)
        channel = self.app_helper.create_channel(supports_generic_sends=True)
        conv_helper = self.app_helper.create_conversation_helper(
            name=u"myconv", started=True, channel=channel, groups=[group])
        response = self.client.get(
            conv_helper.get_action_view_url('send_survey'))
        conversation = response.context[0].get('conversation')
        self.assertEqual(conversation.name, u"myconv")
        self.assertEqual([], self.app_helper.get_api_commands_sent())

    def test_action_send_survey_post(self):
        group = self.app_helper.create_group_with_contacts(u'test_group', 0)
        channel = self.app_helper.create_channel(supports_generic_sends=True)
        conv_helper = self.app_helper.create_conversation_helper(
            started=True, channel=channel, groups=[group])
        response = self.client.post(
            conv_helper.get_action_view_url('send_survey'), {}, follow=True)
        self.assertRedirects(response, conv_helper.get_view_url('show'))
        [send_survey_cmd] = self.app_helper.get_api_commands_sent()
        conversation = conv_helper.get_conversation()
        self.assertEqual(send_survey_cmd, VumiApiCommand.command(
            '%s_application' % (conversation.conversation_type,),
            'send_survey', command_id=send_survey_cmd["command_id"],
            user_account_key=conversation.user_account.key,
            conversation_key=conversation.key,
            batch_id=conversation.batch.key, msg_options={},
            delivery_class=conversation.delivery_class))

    def test_action_send_survey_no_group(self):
        channel = self.app_helper.create_channel(supports_generic_sends=True)
        conv_helper = self.app_helper.create_conversation_helper(
            started=True, channel=channel)
        response = self.client.post(
            conv_helper.get_action_view_url('send_survey'), {}, follow=True)
        self.assertRedirects(response, conv_helper.get_view_url('show'))
        [msg] = response.context['messages']
        self.assertEqual(
            str(msg), "Action disabled: This action needs a contact group.")
        self.assertEqual([], self.app_helper.get_api_commands_sent())

    def test_action_send_survey_not_running(self):
        group = self.app_helper.create_group_with_contacts(u'test_group', 0)
        channel = self.app_helper.create_channel(supports_generic_sends=True)
        conv_helper = self.app_helper.create_conversation_helper(
            started=False, channel=channel, groups=[group])
        response = self.client.post(
            conv_helper.get_action_view_url('send_survey'), {}, follow=True)
        self.assertRedirects(response, conv_helper.get_view_url('show'))
        [msg] = response.context['messages']
        self.assertEqual(
            str(msg),
            "Action disabled: This action needs a running conversation.")
        self.assertEqual([], self.app_helper.get_api_commands_sent())

    def test_action_send_survey_no_channel(self):
        group = self.app_helper.create_group_with_contacts(u'test_group', 0)
        conv_helper = self.app_helper.create_conversation_helper(
            started=True, groups=[group])
        response = self.client.post(
            conv_helper.get_action_view_url('send_survey'), {}, follow=True)
        self.assertRedirects(response, conv_helper.get_view_url('show'))
        [msg] = response.context['messages']
        self.assertEqual(
            str(msg),
            "Action disabled: This action needs channels capable"
            " of sending messages attached to this conversation.")
        self.assertEqual([], self.app_helper.get_api_commands_sent())

    def test_show_stopped(self):
        """
        Test showing the conversation
        """
        conv_helper = self.app_helper.create_conversation_helper(
            name=u"myconv")
        response = self.client.get(conv_helper.get_view_url('show'))
        conversation = response.context[0].get('conversation')
        self.assertEqual(conversation.name, u"myconv")
        self.assertNotContains(
            response, conv_helper.get_action_view_url('send_survey'))

    def test_show_running(self):
        """
        Test showing the conversation
        """
        group = self.app_helper.create_group_with_contacts(u'test_group', 0)
        channel = self.app_helper.create_channel(supports_generic_sends=True)
        conv_helper = self.app_helper.create_conversation_helper(
            name=u"myconv", started=True, channel=channel, groups=[group])
        response = self.client.get(conv_helper.get_view_url('show'))
        conversation = response.context[0].get('conversation')
        self.assertEqual(conversation.name, u"myconv")
        self.assertContains(
            response, conv_helper.get_action_view_url('send_survey'))

    def test_edit_get(self):
        conv_helper = self.app_helper.create_conversation_helper()
        response = self.client.get(conv_helper.get_view_url('edit'))
        # poll_form
        self.assertContains(response, "repeatable")
        self.assertContains(response, "Can contacts interact repeatedly?")
        self.assertContains(response, "case_sensitive")
        self.assertContains(response,
                            "Are the valid responses for each question case"
                            " sensitive?")
        # question forms
        self.assertContains(response, "Question 1:")
        self.assertContains(response, "questions-TOTAL_FORMS")
        # completed survey forms
        self.assertContains(response, "Closing Response 1:")
        self.assertContains(response, "completed_response-TOTAL_FORMS")

    def test_edit(self):
        conv_helper = self.app_helper.create_conversation_helper()
        response = self.client.post(conv_helper.get_view_url('edit'), {
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
        self.assertRedirects(response, conv_helper.get_view_url('show'))
        poll_id = 'poll-%s' % (conv_helper.conversation_key,)
        pm, config = get_poll_config(poll_id)
        [question] = config['questions']
        self.assertEqual(question['copy'], 'What is your favorite music?')
        self.assertEqual(question['valid_responses'], [
            'rock', 'jazz', 'techno'])
        self.assertEqual(question['label'], 'favorite music')

    def test_edit_continue_editing(self):
        conv_helper = self.app_helper.create_conversation_helper()
        response = self.client.post(conv_helper.get_view_url('edit'), {
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
        self.assertRedirects(response, conv_helper.get_view_url('edit'))
        poll_id = 'poll-%s' % (conv_helper.conversation_key,)
        pm, config = get_poll_config(poll_id)
        [question] = config['questions']
        self.assertEqual(question['copy'], 'What is your favorite music?')
        self.assertEqual(question['valid_responses'], [
            'rock', 'jazz', 'techno'])
        self.assertEqual(question['label'], 'favorite music')

    def test_action_export_user_data_get(self):
        group = self.app_helper.create_group_with_contacts(u'test_group', 0)
        channel = self.app_helper.create_channel(supports_generic_sends=True)
        conv_helper = self.app_helper.create_conversation_helper(
            name=u"myconv", started=True, channel=channel, groups=[group])
        response = self.client.get(
            conv_helper.get_action_view_url('download_user_data'))
        conversation = response.context[0].get('conversation')
        self.assertEqual(conversation.name, u"myconv")
        self.assertEqual([], self.app_helper.get_api_commands_sent())
        self.assertContains(response, '>Send CSV via e-mail</button>')

    def setup_poll(self, conv, questions=2, answer=False, user='user-1'):
        question_numbers = list(range(1, 1 + questions))
        pm, poll = self.create_poll(conv, questions=[
            {
                'copy': 'question-%d' % i,
                'label': 'label-%d' % i,
            } for i in question_numbers
        ])

        if answer:
            participant = pm.get_participant(poll.poll_id, user)
            participant.has_unanswered_question = True
            participant.set_last_question_index(0)
            for i in question_numbers:
                poll.submit_answer(participant, 'answer %d' % i)
                participant.set_last_question_index(i)

    def check_csv_email(self, headers, answers, user='user-1'):
        [email] = mail.outbox
        [(file_name, contents, mime_type)] = email.attachments

        self.assertEqual(file_name, 'survey-data-export.zip')

        zipfile = ZipFile(StringIO(contents), 'r')
        csv_contents = zipfile.open('survey-data-export.csv', 'r').read()

        lines = csv_contents.split('\r\n')
        self.assertEqual(lines[0], ','.join(headers))
        self.assertTrue(lines[1].startswith('user-1,'))
        self.assertTrue(lines[1].endswith(',' + ','.join(answers)))

    def test_action_export_user_data_post(self):
        conv_helper = self.app_helper.create_conversation_helper()
        conversation = conv_helper.get_conversation()
        self.setup_poll(conversation, questions=2, answer=True)

        response = self.client.post(
            conv_helper.get_action_view_url('download_user_data'))

        self.assertRedirects(response, conv_helper.get_view_url('show'))
        self.check_csv_email(
            headers=['user_id', 'user_timestamp', 'label-1', 'label-2'],
            answers=['answer 1', 'answer 2'],
        )

    def test_action_export_user_data_post_with_old_questions(self):
        conv_helper = self.app_helper.create_conversation_helper()
        conversation = conv_helper.get_conversation()
        self.setup_poll(conversation, questions=2, answer=True)

        # overwrite poll
        pm, poll = self.create_poll(conversation, questions=[{
                'copy': 'question-1',
                'label': 'label-1',
            }])

        response = self.client.post(
            conv_helper.get_action_view_url('download_user_data'),
            {'include_old_questions': True})

        self.assertRedirects(response, conv_helper.get_view_url('show'))
        self.check_csv_email(
            headers=['user_id', 'user_timestamp', 'label-1', 'label-2'],
            answers=['answer 1', 'answer 2'],
        )
