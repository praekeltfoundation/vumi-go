from StringIO import StringIO

from go.vumitools.tests.helpers import djangotest_imports

with djangotest_imports(globals()):
    from django.core.management.base import CommandError

    from go.base.management.commands import go_manage_http_api
    from go.base.tests.helpers import GoDjangoTestCase, DjangoVumiApiHelper


class TestGoManageHttpAPICommand(GoDjangoTestCase):

    def setUp(self):
        self.vumi_helper = self.add_helper(DjangoVumiApiHelper())
        self.user_helper = self.vumi_helper.make_django_user()
        self.user_email = self.user_helper.get_django_user().email

        self.command = go_manage_http_api.Command()
        self.command.stdout = StringIO()
        self.command.stderr = StringIO()

    def setup_conv(self, **kwargs):
        self.conversation = self.user_helper.create_conversation(
            conversation_type=u'http_api', **kwargs)

    def test_conv_sanity_checks(self):
        self.assertRaisesRegexp(
            CommandError,
            'User matching query does not exist', self.command.handle,
            email_address='foo@bar')
        self.assertRaisesRegexp(
            CommandError, 'Conversation does not exist',
            self.command.handle, email_address=self.user_email,
            conversation_key='foo')

        self.setup_conv()
        self.assertEqual(None, self.command.handle(
            email_address=self.user_email,
            conversation_key=self.conversation.key))

        self.set_conv_type(u'jsbox')
        self.assertEqual(None, self.command.handle(
            email_address=self.user_email,
            conversation_key=self.conversation.key))

        self.set_conv_type(u'bulk_message')
        self.assertRaisesRegexp(
            CommandError,
            'Conversation is not allowed for an HTTP API', self.command.handle,
            email_address=self.user_email,
            conversation_key=self.conversation.key)

    def set_conv_type(self, conv_type):
        self.conversation.c.conversation_type = conv_type
        self.conversation.save()

    def do_command(self, **kwargs):
        return self.command.handle(
            email_address=self.user_email,
            conversation_key=self.conversation.key, **kwargs)

    def test_create_token(self):
        self.setup_conv()
        self.do_command(create_token=True)
        self.assertTrue(
            self.command.stdout.getvalue().startswith('Created token'))
        c = self.user_helper.get_conversation(self.conversation.key)
        self.assertNotEqual(c.config['http_api']['api_tokens'], [])

    def test_remove_token(self):
        self.setup_conv(config={
            'http_api': {
                'api_tokens': ['token'],
            }
        })
        self.do_command(remove_token='token')
        self.assertTrue(
            self.command.stdout.getvalue().startswith('Removed token'))
        c = self.user_helper.get_conversation(self.conversation.key)
        self.assertEqual(c.config['http_api']['api_tokens'], [])

    def test_remove_invalid_token(self):
        self.setup_conv()
        self.assertRaisesRegexp(CommandError, 'Token does not exist',
                                self.do_command, remove_token='foo')

    def test_set_and_remove_message_url(self):
        self.setup_conv()
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
        self.setup_conv()
        self.do_command(set_event_url='http://foo/')
        self.assertEqual(self.command.stdout.getvalue(),
                         'Saved push_event_url: http://foo/')
        self.command.stdout = StringIO()
        self.do_command(remove_event_url=True)
        self.assertEqual(self.command.stdout.getvalue(),
                         'Removed push_event_url: http://foo/')
        self.assertRaisesRegexp(CommandError, 'push_event_url not set',
                                self.do_command, remove_event_url=True)
