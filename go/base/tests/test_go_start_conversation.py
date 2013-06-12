from StringIO import StringIO

from django.core.management.base import CommandError

from go.apps.tests.base import DjangoGoApplicationTestCase
from go.base.management.commands import go_start_conversation

from mock import patch


class DummyMessageSender(object):
    def __init__(self):
        self.outbox = []

    def send_command(self, command):
        self.outbox.append(command)


class GoStartConversationTestCase(DjangoGoApplicationTestCase):

    USE_RIAK = True

    def setUp(self):
        super(GoStartConversationTestCase, self).setUp()
        self.setup_riak_fixtures()
        self.config = self.mk_config({})
        self.command = go_start_conversation.Command()
        self.command.stdout = StringIO()
        self.command.stderr = StringIO()

    def get_conversation(self):
        return self.user_api.get_wrapped_conversation(self.conv_key)

    def test_sanity_checks(self):
        self.assertRaisesRegexp(CommandError, 'provide --email-address',
            self.command.handle, email_address=None, conversation_key=None)
        self.assertRaisesRegexp(CommandError, 'provide --conversation-key',
            self.command.handle, email_address=self.user.username,
            conversation_key=None)
        self.assertRaisesRegexp(CommandError, 'Conversation does not exist',
            self.command.handle, email_address=self.user.username,
            conversation_key='foo')

    @patch('go.vumitools.api.SyncMessageSender')
    def test_start_conversation(self, SyncMessageSender):
        sender = DummyMessageSender()
        SyncMessageSender.return_value = sender
        conversation = self.get_conversation()
        self.assertEqual(conversation.get_tags(), [])
        self.assertEqual(conversation.archive_status, 'active')
        self.assertEqual(conversation.get_status(), 'stopped')
        self.command.handle(
            email_address=self.user.username,
            conversation_key=conversation.key,
            skip_initial_action_hack=False)
        # reload b/c DB changed
        conversation = self.get_conversation()
        self.assertEqual(conversation.get_status(), 'starting')
        [(pool, tag)] = conversation.get_tags()
        self.assertEqual(pool, 'longcode')
        self.assertTrue(tag)
        [start_command, hack_command] = sender.outbox
        self.assertEqual(start_command['command'], 'start')
        self.assertEqual(hack_command['command'], 'initial_action_hack')

    @patch('go.vumitools.api.SyncMessageSender')
    def test_start_conversation_skip_iah(self, SyncMessageSender):
        sender = DummyMessageSender()
        SyncMessageSender.return_value = sender
        conversation = self.get_conversation()
        self.assertEqual(conversation.get_tags(), [])
        self.assertEqual(conversation.archive_status, 'active')
        self.assertEqual(conversation.get_status(), 'stopped')
        self.command.handle(
            email_address=self.user.username,
            conversation_key=conversation.key,
            skip_initial_action_hack=True)
        # reload b/c DB changed
        conversation = self.get_conversation()
        self.assertEqual(conversation.get_status(), 'starting')
        [(pool, tag)] = conversation.get_tags()
        self.assertEqual(pool, 'longcode')
        self.assertTrue(tag)
        [start_command] = sender.outbox
        self.assertEqual(start_command['command'], 'start')

    @patch('go.vumitools.api.SyncMessageSender')
    def test_restart_conversation(self, SyncMessageSender):
        sender = DummyMessageSender()
        SyncMessageSender.return_value = sender
        conversation = self.get_conversation()
        conversation.start()

        # Set the status manually, because it's in `starting', not `running'
        conversation.set_status_started()
        conversation.save()

        self.assertRaisesRegexp(
            CommandError, 'Conversation already started',
            self.command.handle, email_address=self.user.username,
            conversation_key=conversation.key, skip_initial_action_hack=False)
