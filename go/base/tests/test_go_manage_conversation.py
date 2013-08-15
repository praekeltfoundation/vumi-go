from pprint import pformat

from mock import patch

from go.base.tests.utils import GoAccountCommandTestCase
from go.base.management.commands import go_manage_conversation


class DummyMessageSender(object):
    def __init__(self):
        self.outbox = []

    def send_command(self, command):
        self.outbox.append(command)


class TestGoManageConversation(GoAccountCommandTestCase):
    command_class = go_manage_conversation.Command

    def test_list(self):
        conv = self.create_conversation()
        expected_output = "0. %s (type: %s, key: %s)\n" % (
            conv.name, conv.conversation_type, conv.key)
        self.assert_command_output(expected_output, 'list')

    def test_show(self):
        conv = self.create_conversation()
        expected_output = "%s\n" % pformat(conv.get_data())
        print expected_output
        self.assert_command_output(
            expected_output, 'show', conversation_key=conv.key)

    def test_show_config_no_conv(self):
        self.assert_command_error(
            'Please specify a conversation key', 'show_config')
        self.assert_command_error(
            'Conversation does not exist',
            'show_config', conversation_key='foo')

    def test_show_config(self):
        conv = self.create_conversation(config={
            'http_api': {'api_tokens': ['token']},
        })
        expected_output = "{u'http_api': {u'api_tokens': [u'token']}}\n"
        self.assert_command_output(
            expected_output, 'show_config', conversation_key=conv.key)

    @patch('go.vumitools.api.SyncMessageSender')
    def test_start_conversation(self, SyncMessageSender):
        conv = self.create_conversation()
        sender = DummyMessageSender()
        SyncMessageSender.return_value = sender
        self.assertEqual(conv.archive_status, 'active')
        self.assertEqual(conv.get_status(), 'stopped')

        self.assert_command_output(
            'Starting conversation...\nConversation started\n',
            'start', conversation_key=conv.key)

        conv = self.user_api.get_wrapped_conversation(conv.key)
        self.assertEqual(conv.get_status(), 'starting')
        [start_command] = sender.outbox
        self.assertEqual(start_command['command'], 'start')

    @patch('go.vumitools.api.SyncMessageSender')
    def test_stop_conversation(self, SyncMessageSender):
        conv = self.create_conversation(started=True)
        sender = DummyMessageSender()
        SyncMessageSender.return_value = sender
        self.assertEqual(conv.archive_status, 'active')
        self.assertEqual(conv.get_status(), 'running')

        self.assert_command_output(
            'Stopping conversation...\nConversation stopped\n',
            'stop', conversation_key=conv.key)

        conv = self.user_api.get_wrapped_conversation(conv.key)
        self.assertEqual(conv.get_status(), 'stopping')
        [stop_command] = sender.outbox
        self.assertEqual(stop_command['command'], 'stop')

    def test_archive_conversation(self):
        conv = self.create_conversation()
        self.assertEqual(conv.archive_status, 'active')
        self.assertEqual(conv.get_status(), 'stopped')

        self.assert_command_output(
            'Archiving conversation...\nConversation archived\n',
            'archive', conversation_key=conv.key)

        conv = self.user_api.get_wrapped_conversation(conv.key)
        self.assertEqual(conv.archive_status, 'archived')
