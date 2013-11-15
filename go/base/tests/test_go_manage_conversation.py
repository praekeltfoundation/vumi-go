from pprint import pformat

from go.base.management.commands import go_manage_conversation
from go.base.tests.helpers import GoAccountCommandTestCase


class TestGoManageConversation(GoAccountCommandTestCase):

    def setUp(self):
        self.setup_command(go_manage_conversation.Command)

    def test_list(self):
        conv = self.user_helper.create_conversation(u"http_api")
        expected_output = "0. %s (type: %s, key: %s)\n" % (
            conv.name, conv.conversation_type, conv.key)
        self.assert_command_output(expected_output, 'list')

    def test_show(self):
        conv = self.user_helper.create_conversation(u"http_api")
        expected_output = "%s\n" % pformat(conv.get_data())
        self.assert_command_output(
            expected_output, 'show', conversation_key=conv.key)

    def test_show_config_no_conv(self):
        self.assert_command_error(
            'Please specify a conversation key', 'show_config')
        self.assert_command_error(
            'Conversation does not exist',
            'show_config', conversation_key='foo')

    def test_show_config(self):
        conv = self.user_helper.create_conversation(u"http_api", config={
            'http_api': {'api_tokens': ['token']},
        })
        expected_output = "{u'http_api': {u'api_tokens': [u'token']}}\n"
        self.assert_command_output(
            expected_output, 'show_config', conversation_key=conv.key)

    def test_start_conversation(self):
        conv = self.user_helper.create_conversation(u"http_api")
        self.assertEqual(conv.archive_status, 'active')
        self.assertEqual(conv.get_status(), 'stopped')

        self.assert_command_output(
            'Starting conversation...\nConversation started\n',
            'start', conversation_key=conv.key)

        conv = self.user_helper.get_conversation(conv.key)
        self.assertEqual(conv.get_status(), 'starting')
        [start_command] = self.vumi_helper.amqp_connection.get_commands()
        self.assertEqual(start_command['command'], 'start')

    def test_stop_conversation(self):
        conv = self.user_helper.create_conversation(u"http_api", started=True)
        self.assertEqual(conv.archive_status, 'active')
        self.assertEqual(conv.get_status(), 'running')

        self.assert_command_output(
            'Stopping conversation...\nConversation stopped\n',
            'stop', conversation_key=conv.key)

        conv = self.user_helper.get_conversation(conv.key)
        self.assertEqual(conv.get_status(), 'stopping')
        [stop_command] = self.vumi_helper.amqp_connection.get_commands()
        self.assertEqual(stop_command['command'], 'stop')

    def test_archive_conversation(self):
        conv = self.user_helper.create_conversation(u"http_api")
        self.assertEqual(conv.archive_status, 'active')
        self.assertEqual(conv.get_status(), 'stopped')

        self.assert_command_output(
            'Archiving conversation...\nConversation archived\n',
            'archive', conversation_key=conv.key)

        conv = self.user_helper.get_conversation(conv.key)
        self.assertEqual(conv.archive_status, 'archived')
