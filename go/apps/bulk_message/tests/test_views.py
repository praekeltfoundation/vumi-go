import datetime

from vumi.tests.utils import RegexMatcher

from go.vumitools.api import VumiApiCommand
from go.vumitools.tests.helpers import djangotest_imports
from go.vumitools.token_manager import TokenManager

with djangotest_imports(globals()):
    from django.core.urlresolvers import reverse
    from go.apps.tests.view_helpers import AppViewsHelper
    from go.base.tests.helpers import GoDjangoTestCase
    from go.scheduler.models import Task
    from go.scheduler.tasks import perform_conversation_action


class TestBulkMessageViews(GoDjangoTestCase):

    def setUp(self):
        self.app_helper = self.add_helper(AppViewsHelper(u'bulk_message'))
        self.client = self.app_helper.get_client()

    def test_show_stopped(self):
        """
        Test showing the conversation
        """
        conv_helper = self.app_helper.create_conversation_helper(
            name=u"myconv")
        response = self.client.get(conv_helper.get_view_url('show'))
        conversation = response.context[0].get('conversation')
        self.assertEqual(conversation.name, u"myconv")
        self.assertContains(response, 'Write and send bulk message')
        self.assertNotContains(
            response, conv_helper.get_action_view_url('bulk_send'))

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
        self.assertContains(response, 'Write and send bulk message')
        self.assertContains(
            response, conv_helper.get_action_view_url('bulk_send'))

    def test_action_bulk_send_view(self):
        group = self.app_helper.create_group_with_contacts(u'test_group', 0)
        channel = self.app_helper.create_channel(supports_generic_sends=True)
        conv_helper = self.app_helper.create_conversation_helper(
            started=True, channel=channel, groups=[group])
        response = self.client.get(
            conv_helper.get_action_view_url('bulk_send'))
        self.assertEqual([], self.app_helper.get_api_commands_sent())
        self.assertContains(response, 'name="message"')
        self.assertContains(response, '<h1>Write and send bulk message</h1>')
        self.assertContains(response, 'name="delivery_class"')
        self.assertContains(response, 'Channel type')
        self.assertContains(response,
                            '<option value="sms" selected="selected">SMS<')
        self.assertContains(response, 'name="dedupe"')
        self.assertContains(response, '>Send message now</button>')
        self.assertContains(response, '>Schedule</button>')

    def test_action_bulk_send_no_group(self):
        conv_helper = self.app_helper.create_conversation_helper(started=True)
        response = self.client.post(
            conv_helper.get_action_view_url('bulk_send'),
            {'message': 'I am ham, not spam.', 'dedupe': True},
            follow=True)
        self.assertRedirects(response, conv_helper.get_view_url('show'))
        [msg] = response.context['messages']
        self.assertEqual(
            str(msg), "Action disabled: This action needs a contact group.")
        self.assertEqual([], self.app_helper.get_api_commands_sent())

    def test_action_bulk_send_not_running(self):
        group = self.app_helper.create_group_with_contacts(u'test_group', 0)
        conv_helper = self.app_helper.create_conversation_helper(
            groups=[group])
        response = self.client.post(
            conv_helper.get_action_view_url('bulk_send'),
            {'message': 'I am ham, not spam.', 'dedupe': True},
            follow=True)
        self.assertRedirects(response, conv_helper.get_view_url('show'))
        [msg] = response.context['messages']
        self.assertEqual(
            str(msg),
            "Action disabled: This action needs a running conversation.")
        self.assertEqual([], self.app_helper.get_api_commands_sent())

    def test_action_bulk_send_no_channel(self):
        group = self.app_helper.create_group_with_contacts(u'test_group', 0)
        conv_helper = self.app_helper.create_conversation_helper(
            started=True, groups=[group])
        response = self.client.post(
            conv_helper.get_action_view_url('bulk_send'),
            {'message': 'I am ham, not spam.', 'dedupe': True},
            follow=True)
        self.assertRedirects(response, conv_helper.get_view_url('show'))
        [msg] = response.context['messages']
        self.assertEqual(
            str(msg),
            "Action disabled: This action needs channels capable of sending"
            " messages attached to this conversation.")
        self.assertEqual([], self.app_helper.get_api_commands_sent())

    def test_action_bulk_send_dedupe(self):
        group = self.app_helper.create_group_with_contacts(u'test_group', 0)
        channel = self.app_helper.create_channel(supports_generic_sends=True)
        conv_helper = self.app_helper.create_conversation_helper(
            started=True, channel=channel, groups=[group])
        response = self.client.post(
            conv_helper.get_action_view_url('bulk_send'),
            {'message': 'I am ham, not spam.', 'delivery_class': 'sms',
             'dedupe': True})
        self.assertRedirects(response, conv_helper.get_view_url('show'))
        [bulk_send_cmd] = self.app_helper.get_api_commands_sent()
        conversation = conv_helper.get_conversation()
        self.assertEqual(bulk_send_cmd, VumiApiCommand.command(
            '%s_application' % (conversation.conversation_type,),
            'bulk_send', command_id=bulk_send_cmd["command_id"],
            user_account_key=conversation.user_account.key,
            conversation_key=conversation.key,
            batch_id=conversation.batch.key, msg_options={},
            delivery_class='sms',
            content='I am ham, not spam.', dedupe=True))

    def test_action_bulk_send_no_dedupe(self):
        group = self.app_helper.create_group_with_contacts(u'test_group', 0)
        channel = self.app_helper.create_channel(supports_generic_sends=True)
        conv_helper = self.app_helper.create_conversation_helper(
            started=True, channel=channel, groups=[group])
        response = self.client.post(
            conv_helper.get_action_view_url('bulk_send'),
            {'message': 'I am ham, not spam.', 'delivery_class': 'sms',
             'dedupe': False})
        self.assertRedirects(response, conv_helper.get_view_url('show'))
        [bulk_send_cmd] = self.app_helper.get_api_commands_sent()
        conversation = conv_helper.get_conversation()
        self.assertEqual(bulk_send_cmd, VumiApiCommand.command(
            '%s_application' % (conversation.conversation_type,),
            'bulk_send', command_id=bulk_send_cmd["command_id"],
            user_account_key=conversation.user_account.key,
            conversation_key=conversation.key,
            batch_id=conversation.batch.key, msg_options={},
            delivery_class='sms',
            content='I am ham, not spam.', dedupe=False))

    def test_action_bulk_send_confirm(self):
        """
        Test action with confirmation required
        """
        # TODO: Break this test into smaller bits and move them to a more
        #       appropriate module.
        user_account = self.app_helper.get_or_create_user().get_user_account()
        user_account.msisdn = u'+27761234567'
        user_account.confirm_start_conversation = True
        user_account.save()

        # Start the conversation
        group = self.app_helper.create_group_with_contacts(u'test_group', 0)
        channel = self.app_helper.create_channel(supports_generic_sends=True)
        conv_helper = self.app_helper.create_conversation_helper(
            started=True, channel=channel, groups=[group])

        # POST the action with a mock token manager
        self.monkey_patch(
            TokenManager, 'generate_token', lambda s: ('abcdef', '123456'))
        response = self.client.post(
            conv_helper.get_action_view_url('bulk_send'),
            {'message': 'I am ham, not spam.', 'delivery_class': 'sms',
             'dedupe': True})
        self.assertRedirects(response, conv_helper.get_view_url('show'))

        # Check that we get a confirmation message
        [token_send_cmd] = self.app_helper.get_api_commands_sent()
        conversation = conv_helper.get_conversation()
        self.assertEqual(
            VumiApiCommand.command(
                '%s_application' % (conversation.conversation_type,),
                'send_message', command_id=token_send_cmd["command_id"],
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
            conv_helper.get_view_url('confirm') + '?token=6-abcdef123456')

        # POST the full token to the confirmation URL
        final_response = self.client.post(
            conv_helper.get_view_url('confirm'), {'token': '6-abcdef123456'})
        self.assertRedirects(final_response, conv_helper.get_view_url('show'))

        [bulk_send_cmd] = self.app_helper.get_api_commands_sent()
        self.assertEqual(bulk_send_cmd, VumiApiCommand.command(
            '%s_application' % (conversation.conversation_type,),
            'bulk_send', command_id=bulk_send_cmd["command_id"],
            user_account_key=conversation.user_account.key,
            conversation_key=conversation.key,
            batch_id=conversation.batch.key, msg_options={},
            delivery_class='sms',
            content='I am ham, not spam.', dedupe=True))

    def test_action_bulk_send_schedule(self):
        group = self.app_helper.create_group_with_contacts(u'test_group', 0)
        channel = self.app_helper.create_channel(supports_generic_sends=True)
        conv_helper = self.app_helper.create_conversation_helper(
            started=True, channel=channel, groups=[group])
        response = self.client.post(
            conv_helper.get_action_view_url('bulk_send'),
            {'message': 'I am ham, not spam.', 'delivery_class': 'sms',
             'dedupe': True, 'scheduled_datetime': '2016-01-13 16:11'})
        self.assertRedirects(response, conv_helper.get_view_url('show'))

        conversation = conv_helper.get_conversation()
        [task] = Task.objects.all()

        perform_conversation_action(task)
        [bulk_send_cmd] = self.app_helper.get_api_commands_sent()
        self.assertEqual(bulk_send_cmd, VumiApiCommand.command(
            '%s_application' % (conversation.conversation_type,),
            'bulk_send', command_id=bulk_send_cmd["command_id"],
            user_account_key=conversation.user_account.key,
            conversation_key=conversation.key,
            batch_id=conversation.batch.key, msg_options={},
            delivery_class='sms',
            content='I am ham, not spam.', dedupe=True))

        self.assertEqual(
            task.account_id, conversation.user_account.key)
        self.assertEqual(task.label, 'Bulk Message Send')
        self.assertEqual(task.task_type, Task.TYPE_CONVERSATION_ACTION)
        self.assertEqual(task.status, Task.STATUS_PENDING)
        self.assertEqual(
            task.scheduled_for, datetime.datetime.strptime(
                '2016-01-13 16:11', '%Y-%m-%d %H:%M'))
