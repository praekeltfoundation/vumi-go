from StringIO import StringIO

from django.core.management.base import CommandError

from go.base.tests.utils import VumiGoDjangoTestCase
from go.base.management.commands import go_start_conversation

from mock import patch


class DummyMessageSender(object):
    def __init__(self):
        self.outbox = []

    def send_command(self, command):
        self.outbox.append(command)


class GoStartConversationTestCase(VumiGoDjangoTestCase):
    use_riak = True

    def setUp(self):
        super(GoStartConversationTestCase, self).setUp()
        self.setup_api()
        self.setup_user_api()

        self.config = self.mk_config({})
        self.command = go_start_conversation.Command()
        self.command.stdout = StringIO()
        self.command.stderr = StringIO()

    def test_sanity_checks(self):
        self.assertRaisesRegexp(CommandError, 'provide --email-address',
            self.command.handle, email_address=None, conversation_key=None)
        self.assertRaisesRegexp(CommandError, 'provide --conversation-key',
            self.command.handle, email_address=self.django_user.username,
            conversation_key=None)
        self.assertRaisesRegexp(CommandError, 'Conversation does not exist',
            self.command.handle, email_address=self.django_user.username,
            conversation_key='foo')

    @patch('go.vumitools.api.SyncMessageSender')
    def test_start_conversation(self, SyncMessageSender):
        conv = self.create_conversation()
        sender = DummyMessageSender()
        SyncMessageSender.return_value = sender
        self.assertEqual(conv.archive_status, 'active')
        self.assertEqual(conv.get_status(), 'stopped')
        self.command.handle(
            email_address=self.django_user.username,
            conversation_key=conv.key)
        # reload b/c DB changed
        conv = self.user_api.get_wrapped_conversation(conv.key)
        self.assertEqual(conv.get_status(), 'starting')
        [start_command] = sender.outbox
        self.assertEqual(start_command['command'], 'start')

    @patch('go.vumitools.api.SyncMessageSender')
    def test_restart_conversation(self, SyncMessageSender):
        conv = self.create_conversation(started=True)
        sender = DummyMessageSender()
        SyncMessageSender.return_value = sender

        self.assertRaisesRegexp(
            CommandError, 'Conversation already started',
            self.command.handle, email_address=self.django_user.username,
            conversation_key=conv.key)
