import datetime
import json

from go.api.go_api.tests.utils import MockRpc
from go.vumitools.api import VumiApiCommand
from go.vumitools.contact.models import DELIVERY_CLASSES
from go.vumitools.tests.helpers import djangotest_imports

with djangotest_imports(globals()):
    from go.apps.tests.view_helpers import AppViewsHelper
    from go.base.tests.helpers import GoDjangoTestCase
    from go.scheduler.models import Task
    from go.scheduler.tasks import perform_conversation_action


class TestDialogueViews(GoDjangoTestCase):

    def setUp(self):
        self.app_helper = self.add_helper(AppViewsHelper(u'dialogue'))
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
            channel = self.app_helper.create_channel(
                supports_generic_sends=True)
        return self.app_helper.create_conversation_helper(
            channel=channel, groups=groups, **kw)

    def test_action_send_dialogue_get(self):
        conv_helper = self.setup_conversation(started=True)
        response = self.client.get(
            conv_helper.get_action_view_url('send_jsbox'))
        self.assertEqual([], self.app_helper.get_api_commands_sent())
        self.assertContains(response, '<h1>Send Dialogue</h1>')
        self.assertContains(response, '>Send dialogue now</button>')
        self.assertContains(response, '>Schedule dialogue send</button>')

    def test_action_send_dialogue_post(self):
        conv_helper = self.setup_conversation(started=True)
        response = self.client.post(
            conv_helper.get_action_view_url('send_jsbox'), {}, follow=True)
        self.assertRedirects(response, conv_helper.get_view_url('show'))
        [send_jsbox_cmd] = self.app_helper.get_api_commands_sent()
        conversation = conv_helper.get_conversation()
        self.assertEqual(send_jsbox_cmd, VumiApiCommand.command(
            '%s_application' % (conversation.conversation_type,),
            'send_jsbox', command_id=send_jsbox_cmd["command_id"],
            user_account_key=conversation.user_account.key,
            conversation_key=conversation.key,
            batch_id=conversation.batch.key))

    def test_action_send_dialogue_schedule(self):
        conv_helper = self.setup_conversation(started=True)
        response = self.client.post(
            conv_helper.get_action_view_url('send_jsbox'), {
                'scheduled_datetime': '2016-01-13 16:11',
            }, follow=True)
        self.assertRedirects(response, conv_helper.get_view_url('show'))

        commands = self.app_helper.get_api_commands_sent()
        self.assertEqual(commands, [])

        conversation = conv_helper.get_conversation()
        [task] = Task.objects.all()

        perform_conversation_action(task)
        [send_jsbox_cmd] = self.app_helper.get_api_commands_sent()
        self.assertEqual(send_jsbox_cmd, VumiApiCommand.command(
            '%s_application' % (conversation.conversation_type,),
            'send_jsbox', command_id=send_jsbox_cmd["command_id"],
            user_account_key=conversation.user_account.key,
            conversation_key=conversation.key,
            batch_id=conversation.batch.key))

        self.assertEqual(
            task.account_id, conversation.user_account.key)
        self.assertEqual(task.label, 'Dialogue Message Send')
        self.assertEqual(task.task_type, Task.TYPE_CONVERSATION_ACTION)
        self.assertEqual(task.status, Task.STATUS_PENDING)
        self.assertEqual(
            task.scheduled_for, datetime.datetime.strptime(
                '2016-01-13 16:11', '%Y-%m-%d %H:%M'))

    def test_action_send_dialogue_no_group(self):
        conv_helper = self.setup_conversation(started=True, with_group=False)
        response = self.client.post(
            conv_helper.get_action_view_url('send_jsbox'), {}, follow=True)
        self.assertRedirects(response, conv_helper.get_view_url('show'))
        [msg] = response.context['messages']
        self.assertEqual(
            str(msg), "Action disabled: This action needs a contact group.")
        self.assertEqual([], self.app_helper.get_api_commands_sent())

    def test_action_send_dialogue_not_running(self):
        conv_helper = self.setup_conversation(started=False)
        response = self.client.post(
            conv_helper.get_action_view_url('send_jsbox'), {},
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
            conv_helper.get_action_view_url('send_jsbox'), {}, follow=True)
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
            response, conv_helper.get_action_view_url('send_jsbox'))

    def test_show_running(self):
        """
        Test showing the conversation
        """
        conv_helper = self.setup_conversation(started=True, name=u"myconv")
        response = self.client.get(conv_helper.get_view_url('show'))
        conversation = response.context[0].get('conversation')
        self.assertEqual(conversation.name, u"myconv")
        self.assertContains(response,
                            conv_helper.get_action_view_url('send_jsbox'))

    def test_edit(self):
        conv_helper = self.setup_conversation(name=u"myconv")
        self.mock_rpc.set_response(result={"poll": {}})
        response = self.client.get(conv_helper.get_view_url('edit'))

        self.assertContains(response, u"myconv")
        self.assertContains(response, 'diagram')

    def test_edit_channel_types(self):
        conv_helper = self.setup_conversation()
        self.mock_rpc.set_response(result={"poll": {}})
        response = self.client.get(conv_helper.get_view_url('edit'))

        for d in DELIVERY_CLASSES.itervalues():
            self.assertContains(response, d['label'])

    def test_edit_model_data(self):
        conv_helper = self.setup_conversation()
        conversation = conv_helper.get_conversation()

        poll = {}
        self.mock_rpc.set_response(result={"poll": poll})
        response = self.client.get(conv_helper.get_view_url('edit'))

        expected = poll.copy()
        expected.update({
            'campaign_id': conversation.user_account.key,
            'conversation_key': conversation.key,
            'urls': {"show": conv_helper.get_view_url('show')}
        })

        model_data = response.context["model_data"]
        self.assertEqual(json.loads(model_data), expected)

    def test_edit_model_data_groups(self):
        conv_helper = self.setup_conversation(
            with_group=False, started=False, name=u"myconv")

        conversation = conv_helper.get_conversation()
        group1 = self.app_helper.create_group(u'group1')
        group2 = self.app_helper.create_group(u'group2')
        conversation.add_group(group1)

        poll = {
            'groups': [{
                'key': '123',
                'name': 'foo'
            }]
        }

        self.mock_rpc.set_response(result={"poll": poll})
        response = self.client.get(conv_helper.get_view_url('edit'))

        expected = poll.copy()
        expected.update({'groups': [group1.get_data(), group2.get_data()]})

        model_data = response.context["model_data"]
        self.assertEqual(json.loads(model_data), expected)

    def test_edit_model_data_channel_types(self):
        conv_helper = self.setup_conversation()

        poll = {}
        self.mock_rpc.set_response(result={"poll": poll})
        response = self.client.get(conv_helper.get_view_url('edit'))

        expected = poll.copy()
        expected.update({
            'channel_types': [{
                'name': name,
                'label': d['label']
            } for name, d in DELIVERY_CLASSES.iteritems()]
        })

        model_data = response.context["model_data"]
        self.assertEqual(json.loads(model_data), expected)
