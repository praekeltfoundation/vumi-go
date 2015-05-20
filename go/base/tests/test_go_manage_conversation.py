import json
from StringIO import StringIO
from pprint import pformat
from datetime import datetime

from django.core.management.base import CommandError

from vumi.message import parse_vumi_date

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

    def test_export(self):
        conv = self.user_helper.create_conversation(u"http_api")
        self.assert_command_output(json.dumps(
            conv.get_data()), 'export', conversation_key=conv.key)

    def test_import(self):
        original = {
            "status": "running",
            "conversation_type": "bulk_message",
            "extra_endpoints": [],
            "description": "hello world",
            "archive_status": "active",
            "created_at": "2013-12-09 13:02:03.332158",
            "batch": "30aae629e8774c56b482a1dfef39875c",
            "name": "conversation name",
            "key": "f7115b8c6cc3442b90655234d1a893ce",
            "groups": [],
            "$VERSION": 3,
            "archived_at": None,
            "delivery_class": None,
            "config": {},
            "user_account": "test-0-user"
        }

        self.command.load_file = lambda *a: StringIO(json.dumps(original))

        self.call_command('import', file='foo.json')

        # get latest conversation
        conversations = self.user_helper.user_api.active_conversations()
        conv = max(conversations, key=lambda c: c.created_at)
        data = conv.get_data()
        created_at = parse_vumi_date(data.pop('created_at'))
        status = data.pop('status')
        batch = data.pop('batch')
        key = data.pop('key')
        groups = data.pop('groups')
        user_account = data.pop('user_account')
        self.assertEqual(created_at.date(), datetime.now().date())
        self.assertEqual(status, 'stopped')
        self.assertEqual(groups, [])
        self.assertNotEqual(batch, original['batch'])
        self.assertNotEqual(key, original['key'])
        self.assertEqual(user_account, self.user_helper.account_key)

    def test_import_invalid_conv_type(self):
        original = {
            "status": "running",
            "conversation_type": "foo",
            "description": "hello world",
            "name": "conversation name",
            "config": {},
        }

        self.command.load_file = lambda *a: StringIO(json.dumps(original))

        self.assertRaisesRegexp(
            CommandError, 'Invalid conversation_type: foo',
            self.call_command, 'import', file='foo.json')
