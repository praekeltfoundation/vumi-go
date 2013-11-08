import json

from go.vumitools.tests.utils import VumiApiCommand
from go.api.go_api.tests.utils import MockRpc
from go.apps.tests.view_helpers import AppViewHelper
from go.base.tests.utils import VumiGoDjangoTestCase


class TestDialogueViews(VumiGoDjangoTestCase):

    use_riak = True

    def setUp(self):
        super(TestDialogueViews, self).setUp()
        self.app_helper = AppViewHelper(self, u'dialogue')
        self.add_cleanup(self.app_helper.cleanup)
        self.client = self.app_helper.get_client()
        self.mock_rpc = MockRpc()
        self.add_cleanup(self.mock_rpc.tearDown)

    def setup_conversation(self, with_group=True, with_channel=True, **kw):
        groups = []
        if with_group:
            groups.append(
                self.app_helper.create_group_with_contacts(u'test_group', 0))
        channel = None
        if with_channel:
            channel = self.app_helper.create_channel({
                "supports": {"generic_sends": True},
            })
        return self.app_helper.create_conversation(
            channel=channel, groups=groups, **kw)

    def test_action_send_dialogue_get(self):
        conv_helper = self.setup_conversation(started=True)
        response = self.client.get(
            conv_helper.get_action_view_url('send_dialogue'))
        self.assertEqual([], self.app_helper.get_api_commands_sent())
        self.assertContains(response, '<h1>Send Dialogue</h1>')

    def test_action_send_dialogue_post(self):
        conv_helper = self.setup_conversation(started=True)
        response = self.client.post(
            conv_helper.get_action_view_url('send_dialogue'), {}, follow=True)
        self.assertRedirects(response, conv_helper.get_view_url('show'))
        [send_dialogue_cmd] = self.app_helper.get_api_commands_sent()
        conversation = conv_helper.get_conversation()
        self.assertEqual(send_dialogue_cmd, VumiApiCommand.command(
            '%s_application' % (conversation.conversation_type,),
            'send_dialogue',
            user_account_key=conversation.user_account.key,
            conversation_key=conversation.key,
            batch_id=conversation.batch.key,
            delivery_class=conversation.delivery_class))

    def test_action_send_dialogue_no_group(self):
        conv_helper = self.setup_conversation(started=True, with_group=False)
        response = self.client.post(
            conv_helper.get_action_view_url('send_dialogue'), {}, follow=True)
        self.assertRedirects(response, conv_helper.get_view_url('show'))
        [msg] = response.context['messages']
        self.assertEqual(
            str(msg), "Action disabled: This action needs a contact group.")
        self.assertEqual([], self.app_helper.get_api_commands_sent())

    def test_action_send_dialogue_not_running(self):
        conv_helper = self.setup_conversation(started=False)
        response = self.client.post(
            conv_helper.get_action_view_url('send_dialogue'), {},
            follow=True)
        self.assertRedirects(response, conv_helper.get_view_url('show'))
        [msg] = response.context['messages']
        self.assertEqual(
            str(msg),
            "Action disabled: This action needs a running conversation.")
        self.assertEqual([], self.app_helper.get_api_commands_sent())

    def test_action_send_dialogue_no_channel(self):
        conv_helper = self.setup_conversation(started=True, with_channel=False)
        response = self.client.post(
            conv_helper.get_action_view_url('send_dialogue'), {}, follow=True)
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
        conv_helper = self.setup_conversation(started=False, name=u"myconv")
        response = self.client.get(conv_helper.get_view_url('show'))
        conversation = response.context[0].get('conversation')
        self.assertEqual(conversation.name, u"myconv")
        self.assertNotContains(
            response, conv_helper.get_action_view_url('send_dialogue'))

    def test_show_running(self):
        """
        Test showing the conversation
        """
        conv_helper = self.setup_conversation(started=True, name=u"myconv")
        response = self.client.get(conv_helper.get_view_url('show'))
        conversation = response.context[0].get('conversation')
        self.assertEqual(conversation.name, u"myconv")
        self.assertContains(response,
                            conv_helper.get_action_view_url('send_dialogue'))

    def test_edit(self):
        conv_helper = self.setup_conversation(started=False, name=u"myconv")
        poll = {"foo": "bar"}
        self.mock_rpc.set_response(result={"poll": poll})
        response = self.client.get(conv_helper.get_view_url('edit'))
        self.assertContains(response, u"myconv")
        self.assertContains(response, 'diagram')

        conversation = conv_helper.get_conversation()
        expected = poll.copy()
        expected["campaign_id"] = conversation.user_account.key
        expected["conversation_key"] = conversation.key
        expected["urls"] = {
            "show": conv_helper.get_view_url('show'),
        }
        model_data = response.context["model_data"]
        self.assertEqual(json.loads(model_data), expected)

    def test_export_user_data(self):
        conv_helper = self.setup_conversation()
        response = self.client.get(conv_helper.get_view_url('user_data'))
        self.assertEqual(response['Content-Type'], 'application/csv')
        self.assertEqual(response.content, "TODO: write data export.")
