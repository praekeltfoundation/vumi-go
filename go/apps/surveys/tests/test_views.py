from StringIO import StringIO
from zipfile import ZipFile

from django.core import mail

from go.apps.surveys.view_definition import get_poll_config
from go.apps.tests.view_helpers import AppViewsHelper
from go.base.tests.helpers import GoDjangoTestCase
from go.vumitools.api import VumiApiCommand


class TestSurveysViews(GoDjangoTestCase):

    def setUp(self):
        self.app_helper = AppViewsHelper(u'survey')
        self.add_cleanup(self.app_helper.cleanup)
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
        channel = self.app_helper.create_channel({
            "supports": {"generic_sends": True},
        })
        conv_helper = self.app_helper.create_conversation(
            name=u"myconv", started=True, channel=channel, groups=[group])
        response = self.client.get(
            conv_helper.get_action_view_url('send_survey'))
        conversation = response.context[0].get('conversation')
        self.assertEqual(conversation.name, u"myconv")
        self.assertEqual([], self.app_helper.get_api_commands_sent())

    def test_action_send_survey_post(self):
        group = self.app_helper.create_group_with_contacts(u'test_group', 0)
        channel = self.app_helper.create_channel({
            "supports": {"generic_sends": True},
        })
        conv_helper = self.app_helper.create_conversation(
            started=True, channel=channel, groups=[group])
        response = self.client.post(
            conv_helper.get_action_view_url('send_survey'), {}, follow=True)
        self.assertRedirects(response, conv_helper.get_view_url('show'))
        [send_survey_cmd] = self.app_helper.get_api_commands_sent()
        conversation = conv_helper.get_conversation()
        self.assertEqual(send_survey_cmd, VumiApiCommand.command(
            '%s_application' % (conversation.conversation_type,),
            'send_survey',
            user_account_key=conversation.user_account.key,
            conversation_key=conversation.key,
            batch_id=conversation.batch.key, msg_options={},
            delivery_class=conversation.delivery_class))

    def test_action_send_survey_no_group(self):
        channel = self.app_helper.create_channel({
            "supports": {"generic_sends": True},
        })
        conv_helper = self.app_helper.create_conversation(
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
        channel = self.app_helper.create_channel({
            "supports": {"generic_sends": True},
        })
        conv_helper = self.app_helper.create_conversation(
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
        conv_helper = self.app_helper.create_conversation(
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
        conv_helper = self.app_helper.create_conversation(name=u"myconv")
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
        channel = self.app_helper.create_channel({
            "supports": {"generic_sends": True},
        })
        conv_helper = self.app_helper.create_conversation(
            name=u"myconv", started=True, channel=channel, groups=[group])
        response = self.client.get(conv_helper.get_view_url('show'))
        conversation = response.context[0].get('conversation')
        self.assertEqual(conversation.name, u"myconv")
        self.assertContains(
            response, conv_helper.get_action_view_url('send_survey'))

    def test_edit(self):
        conv_helper = self.app_helper.create_conversation()
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
        conv_helper = self.app_helper.create_conversation()
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
        channel = self.app_helper.create_channel({
            "supports": {"generic_sends": True},
        })
        conv_helper = self.app_helper.create_conversation(
            name=u"myconv", started=True, channel=channel, groups=[group])
        response = self.client.get(
            conv_helper.get_action_view_url('download_user_data'))
        conversation = response.context[0].get('conversation')
        self.assertEqual(conversation.name, u"myconv")
        self.assertEqual([], self.app_helper.get_api_commands_sent())
        self.assertContains(response, '>Send CSV via e-mail</button>')

    def test_action_export_user_data_post(self):
        conv_helper = self.app_helper.create_conversation()
        conversation = conv_helper.get_conversation()
        pm, poll = self.create_poll(conversation, questions=[{
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

        response = self.client.post(
            conv_helper.get_action_view_url('download_user_data'))

        self.assertRedirects(response, conv_helper.get_view_url('show'))

        [email] = mail.outbox
        [(file_name, contents, mime_type)] = email.attachments

        self.assertEqual(file_name, 'survey-data-export.zip')

        zipfile = ZipFile(StringIO(contents), 'r')
        csv_contents = zipfile.open('survey-data-export.csv', 'r').read()

        lines = csv_contents.split('\r\n')
        self.assertEqual(lines[0], 'user_id,user_timestamp,label-1,label-2')
        self.assertTrue(lines[1].startswith('user-1'))
        self.assertTrue(lines[1].endswith(',answer 1,answer 2'))
