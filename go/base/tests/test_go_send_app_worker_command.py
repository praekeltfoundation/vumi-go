# -*- coding: utf-8 -*-
from StringIO import StringIO

from django.core.management.base import CommandError

from go.base.tests.utils import VumiGoDjangoTestCase
from go.base.management.commands import go_send_app_worker_command


class DummyMessageSender(object):
    def __init__(self):
        self.outbox = []

    def send_command(self, command):
        self.outbox.append(command)


class GoSendAppWorkerCommandTestCase(VumiGoDjangoTestCase):
    use_riak = True

    def setUp(self):
        super(GoSendAppWorkerCommandTestCase, self).setUp()
        self.setup_api()
        self.setup_user_api()
        self.account_key = self.user_api.user_account_key

        self.command = go_send_app_worker_command.Command()
        self.command.sender_class = DummyMessageSender
        self.command.allowed_commands = ['good_command']
        self.command.stdout = StringIO()
        self.command.stderr = StringIO()

    def test_invalid_command(self):
        self.assertRaisesRegexp(CommandError, 'Unknown command bad_command',
            self.command.handle, 'worker-name', 'bad_command',
            'key=1', 'key=2')

    def test_reconcile_cache_invalid_user(self):
        self.assertRaisesRegexp(CommandError, 'Account does not exist',
            self.command.handle, 'worker-name', 'reconcile_cache',
            'account_key=foo', 'conversation_key=bar')

    def test_reconcile_cache_invalid_conversation(self):
        self.assertRaisesRegexp(CommandError, 'Conversation does not exist',
            self.command.handle, 'worker-name', 'reconcile_cache',
            'account_key=%s' % self.account_key, 'conversation_key=bar')

    def test_reconcile_cache(self):
        conv = self.create_conversation()
        self.command.handle('worker-name', 'reconcile_cache',
            'account_key=%s' % (self.account_key,),
            'conversation_key=%s' % (conv.key,))
        self.assertEqual(self.command.stderr.getvalue(), '')
        self.assertEqual(self.command.stdout.getvalue(), '')
        [cmd] = self.command.sender.outbox
        self.assertEqual(cmd['worker_name'], 'worker-name')
        self.assertEqual(cmd['command'], 'reconcile_cache')
        self.assertEqual(cmd['args'], [])
        self.assertEqual(cmd['kwargs'], {
            'user_account_key': self.account_key,
            'conversation_key': conv.key,
        })
