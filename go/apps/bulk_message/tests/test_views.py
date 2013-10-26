from django.core.urlresolvers import reverse

from vumi.tests.utils import RegexMatcher

from go.vumitools.tests.utils import VumiApiCommand
from go.vumitools.token_manager import TokenManager
from go.apps.tests.base import DjangoGoApplicationTestCase


class BulkMessageTestCase(DjangoGoApplicationTestCase):

    TEST_CONVERSATION_TYPE = u'bulk_message'
    TEST_CHANNEL_METADATA = {
        "supports": {
            "generic_sends": True,
        },
    }

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

    def test_action_bulk_send_view(self):
        self.setup_conversation(started=True, with_group=True,
                                with_channel=True)
        response = self.client.get(self.get_action_view_url('bulk_send'))
        conversation = response.context[0].get('conversation')
        self.assertEqual(conversation.name, self.TEST_CONVERSATION_NAME)
        self.assertEqual([], self.get_api_commands_sent())
        self.assertContains(response, 'name="message"')
        self.assertContains(response, '<h1>Write and send bulk message</h1>')
        self.assertContains(response, '>Send message</button>')

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
        self.monkey_patch(
            TokenManager, 'generate_token', lambda s: ('abcdef', '123456'))
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
