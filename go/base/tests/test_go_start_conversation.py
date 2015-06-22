from StringIO import StringIO

from django.core.management.base import CommandError

from go.base.management.commands import go_start_conversation
from go.base.tests.helpers import GoDjangoTestCase, DjangoVumiApiHelper


class TestGoStartConversation(GoDjangoTestCase):

    def setUp(self):
        self.vumi_helper = self.add_helper(DjangoVumiApiHelper())
        self.user_helper = self.vumi_helper.make_django_user()
        self.user_email = self.user_helper.get_django_user().email

        self.command = go_start_conversation.Command()
        self.command.stdout = StringIO()
        self.command.stderr = StringIO()

    def test_sanity_checks(self):
        self.assertRaisesRegexp(CommandError, 'provide --conversation-key',
            self.command.handle, email_address=self.user_email,
            conversation_key=None)
        self.assertRaisesRegexp(CommandError, 'Conversation does not exist',
            self.command.handle, email_address=self.user_email,
            conversation_key='foo')

    def test_start_conversation(self):
        conv = self.user_helper.create_conversation(u'bulk_message')
        self.assertEqual(conv.archive_status, 'active')
        self.assertEqual(conv.get_status(), 'stopped')
        self.command.handle(
            email_address=self.user_email,
            conversation_key=conv.key)
        # reload b/c DB changed
        conv = self.user_helper.get_conversation(conv.key)
        self.assertEqual(conv.get_status(), 'starting')
        [start_command] = self.vumi_helper.amqp_connection.get_commands()
        self.assertEqual(start_command['command'], 'start')

    def test_restart_conversation(self):
        conv = self.user_helper.create_conversation(
            u'bulk_message', started=True)

        self.assertRaisesRegexp(
            CommandError, 'Conversation already started',
            self.command.handle, email_address=self.user_email,
            conversation_key=conv.key)
