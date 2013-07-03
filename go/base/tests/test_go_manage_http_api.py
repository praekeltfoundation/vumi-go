from StringIO import StringIO

from django.core.management.base import CommandError

from go.apps.tests.base import DjangoGoApplicationTestCase
from go.base.management.commands import go_manage_http_api


class GoManageHttpAPICommandTestCase(DjangoGoApplicationTestCase):
    # TODO: Stop abusing DjangoGoApplicationTestCase for this.

    def setUp(self):
        super(GoManageHttpAPICommandTestCase, self).setUp()
        self.command = go_manage_http_api.Command()
        self.command.stdout = StringIO()
        self.command.stderr = StringIO()

    def test_conv_sanity_checks(self):
        self.setup_conversation()
        self.assertRaisesRegexp(
            CommandError,
            'User matching query does not exist', self.command.handle,
            email_address='foo@bar')
        self.assertRaisesRegexp(
            CommandError, 'Conversation does not exist',
            self.command.handle, email_address=self.django_user.email,
            conversation_key='foo')
        self.assertRaisesRegexp(
            CommandError,
            'Conversation is not allowed for an HTTP API', self.command.handle,
            email_address=self.django_user.email,
            conversation_key=self.conversation.key)

        self.set_conv_type(u'http_api')
        self.assertEqual(None, self.command.handle(
            email_address=self.django_user.email,
            conversation_key=self.conversation.key))

        self.set_conv_type(u'jsbox')
        self.assertEqual(None, self.command.handle(
            email_address=self.django_user.email,
            conversation_key=self.conversation.key))

    def set_conv_type(self, conv_type):
        conv = self.get_wrapped_conv(self.conversation.key)
        conv.c.conversation_type = conv_type
        conv.save()

    def do_command(self, **kwargs):
        self.set_conv_type(u'http_api')
        return self.command.handle(email_address=self.django_user.email,
                                   conversation_key=self.conversation.key,
                                   **kwargs)

    def test_create_token(self):
        self.setup_conversation()
        self.do_command(create_token=True)
        self.assertTrue(
            self.command.stdout.getvalue().startswith('Created token'))

    def test_remove_token(self):
        self.setup_conversation()
        conv = self.get_wrapped_conv()
        conv.set_config({
            'http_api': {
                'api_tokens': ['token'],
            }
        })
        conv.save()
        self.do_command(remove_token='token')
        self.assertTrue(
            self.command.stdout.getvalue().startswith('Removed token'))

    def test_remove_invalid_token(self):
        self.setup_conversation()
        self.assertRaisesRegexp(CommandError, 'Token does not exist',
                                self.do_command, remove_token='foo')

    def test_set_and_remove_message_url(self):
        self.setup_conversation()
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
        self.setup_conversation()
        self.do_command(set_event_url='http://foo/')
        self.assertEqual(self.command.stdout.getvalue(),
                         'Saved push_event_url: http://foo/')
        self.command.stdout = StringIO()
        self.do_command(remove_event_url=True)
        self.assertEqual(self.command.stdout.getvalue(),
                         'Removed push_event_url: http://foo/')
        self.assertRaisesRegexp(CommandError, 'push_event_url not set',
                                self.do_command, remove_event_url=True)
