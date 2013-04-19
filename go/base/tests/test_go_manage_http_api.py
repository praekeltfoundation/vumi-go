from StringIO import StringIO

from django.core.management.base import CommandError

from go.apps.tests.base import DjangoGoApplicationTestCase
from go.base.management.commands import go_manage_http_api
from go.base.utils import vumi_api_for_user


class GoManageHttpAPICommandTestCase(DjangoGoApplicationTestCase):

    USE_RIAK = True

    def setUp(self):
        super(GoManageHttpAPICommandTestCase, self).setUp()
        self.setup_riak_fixtures()
        self.user_api = vumi_api_for_user(self.user)
        self.profile = self.user.get_profile()
        self.command = go_manage_http_api.Command()
        self.command.stdout = StringIO()
        self.command.stderr = StringIO()
        self.conversation = self.user_api.wrap_conversation(self.conversation)

    def test_conv_sanity_checks(self):
        self.assertRaisesRegexp(
            CommandError,
            'User matching query does not exist', self.command.handle,
            email_address='foo@bar')
        self.assertRaisesRegexp(
            CommandError, 'Conversation does not exist',
            self.command.handle, email_address=self.user.email,
            conversation_key='foo')
        self.assertRaisesRegexp(
            CommandError,
            'Conversation is not allowed for an HTTP API', self.command.handle,
            email_address=self.user.email,
            conversation_key=self.conversation.key)

        self.set_conv_type(self.conversation, u'http_api')
        self.assertEqual(None, self.command.handle(
            email_address=self.user.email,
            conversation_key=self.conversation.key))

        self.set_conv_type(self.conversation, u'jsbox')
        self.assertEqual(None, self.command.handle(
            email_address=self.user.email,
            conversation_key=self.conversation.key))

    def set_conv_type(self, conversation, conv_type):
        conv = self.user_api.get_wrapped_conversation(conversation.key)
        conv.c.conversation_type = conv_type
        conv.save()

    def do_command(self, **kwargs):
        self.set_conv_type(self.conversation, u'http_api')
        return self.command.handle(email_address=self.user.email,
                                   conversation_key=self.conversation.key,
                                   **kwargs)

    def test_create_token(self):
        self.do_command(create_token=True)
        self.assertTrue(
            self.command.stdout.getvalue().startswith('Created token'))

    def test_remove_token(self):
        self.conversation.set_metadata({
            'http_api': {
                'api_tokens': ['token'],
            }
        })
        self.conversation.save()
        self.do_command(remove_token='token')
        self.assertTrue(
            self.command.stdout.getvalue().startswith('Removed token'))

    def test_remove_invalid_token(self):
        self.assertRaisesRegexp(CommandError, 'Token does not exist',
                                self.do_command, remove_token='foo')

    def test_set_and_remove_message_url(self):
        self.do_command(set_message_url='http://foo/')
        self.assertEqual(self.command.stdout.getvalue(),
                         'Saved push_message_url: http://foo/')
        self.command.stdout = StringIO()
        self.do_command(remove_message_url=True)
        self.assertEqual(self.command.stdout.getvalue(),
                         'Removed push_message_url: http://foo/')
        self.assertRaisesRegexp(CommandError, 'push_message_url not set',
                                self.do_command, remove_message_url=True)

    def test_set_and_remove_event_url(self):
        self.do_command(set_event_url='http://foo/')
        self.assertEqual(self.command.stdout.getvalue(),
                         'Saved push_event_url: http://foo/')
        self.command.stdout = StringIO()
        self.do_command(remove_event_url=True)
        self.assertEqual(self.command.stdout.getvalue(),
                         'Removed push_event_url: http://foo/')
        self.assertRaisesRegexp(CommandError, 'push_event_url not set',
                                self.do_command, remove_event_url=True)
