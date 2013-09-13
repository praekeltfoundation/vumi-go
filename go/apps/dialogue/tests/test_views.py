import json

from go.vumitools.tests.utils import VumiApiCommand
from go.api.go_api.tests.utils import MockRpc
from go.apps.tests.base import DjangoGoApplicationTestCase


class DialogueTestCase(DjangoGoApplicationTestCase):

    TEST_CONVERSATION_TYPE = u'dialogue'
    TEST_CHANNEL_METADATA = {
        "supports": {
            "generic_sends": True,
        },
    }

    def setUp(self):
        super(DialogueTestCase, self).setUp()
        self.mock_rpc = MockRpc()

    def tearDown(self):
        super(DialogueTestCase, self).tearDown()
        self.mock_rpc.tearDown()

    def check_model_data(self, response, conv, poll):
        expected = poll.copy()
        expected["campaign_id"] = self.user_api.user_account_key
        expected["conversation_key"] = conv.key
        expected["urls"] = {
            "show": self.get_view_url('show')
        }
        model_data = response.context["model_data"]
        self.assertEqual(json.loads(model_data), expected)

    def test_action_send_dialogue_get(self):
        self.setup_conversation(started=True, with_group=True,
                                with_channel=True)
        response = self.client.get(self.get_action_view_url('send_dialogue'))
        conversation = response.context[0].get('conversation')
        self.assertEqual(conversation.name, self.TEST_CONVERSATION_NAME)
        self.assertEqual([], self.get_api_commands_sent())

    def test_action_send_dialogue_post(self):
        self.setup_conversation(started=True, with_group=True,
                                with_channel=True)
        response = self.client.post(
            self.get_action_view_url('send_dialogue'), {}, follow=True)
        self.assertRedirects(response, self.get_view_url('show'))
        [send_dialogue_cmd] = self.get_api_commands_sent()
        conversation = self.get_wrapped_conv()
        self.assertEqual(send_dialogue_cmd, VumiApiCommand.command(
            '%s_application' % (conversation.conversation_type,),
            'send_dialogue',
            user_account_key=conversation.user_account.key,
            conversation_key=conversation.key,
            batch_id=conversation.batch.key,
            delivery_class=conversation.delivery_class))

    def test_action_send_dialogue_no_group(self):
        self.setup_conversation(started=True)
        response = self.client.post(
            self.get_action_view_url('send_dialogue'), {}, follow=True)
        self.assertRedirects(response, self.get_view_url('show'))
        [msg] = response.context['messages']
        self.assertEqual(
            str(msg), "Action disabled: This action needs a contact group.")
        self.assertEqual([], self.get_api_commands_sent())

    def test_action_send_dialogue_not_running(self):
        self.setup_conversation(with_group=True)
        response = self.client.post(
            self.get_action_view_url('send_dialogue'), {}, follow=True)
        self.assertRedirects(response, self.get_view_url('show'))
        [msg] = response.context['messages']
        self.assertEqual(
            str(msg),
            "Action disabled: This action needs a running conversation.")
        self.assertEqual([], self.get_api_commands_sent())

    def test_action_send_dialogue_no_channel(self):
        self.setup_conversation(started=True, with_group=True)
        response = self.client.post(
            self.get_action_view_url('send_dialogue'), {}, follow=True)
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
            response, self.get_action_view_url('send_dialogue'))

    def test_show_running(self):
        """
        Test showing the conversation
        """
        self.setup_conversation(started=True, with_group=True,
                                with_channel=True)
        response = self.client.get(self.get_view_url('show'))
        conversation = response.context[0].get('conversation')
        self.assertEqual(conversation.name, 'Test Conversation')
        self.assertContains(response,
                            self.get_action_view_url('send_dialogue'))

    def test_edit(self):
        self.setup_conversation()
        poll = {"foo": "bar"}
        self.mock_rpc.set_response(result={"poll": poll})
        response = self.client.get(self.get_view_url('edit'))
        conversation = response.context[0].get('conversation')
        self.assertEqual(conversation.name, 'Test Conversation')
        self.assertContains(response, 'Test Conversation')
        self.assertContains(response, 'diagram')
        self.check_model_data(response, conversation, poll)

    def test_export_user_data(self):
        self.setup_conversation()

        response = self.client.get(self.get_view_url('user_data'))
        self.assertEqual(response['Content-Type'], 'application/csv')
        self.assertEqual(response.content, "TODO: write data export.")
