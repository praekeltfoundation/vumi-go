# -*- coding: utf-8 -*-
from StringIO import StringIO

from django.core.management.base import CommandError

from go.base.management.commands import go_send_app_worker_command
from go.apps.tests.base import DjangoGoApplicationTestCase


class DummyMessageSender(object):
    def __init__(self):
        self.outbox = []

    def send_command(self, command):
        self.outbox.append(command)


class GoSendAppWorkerCommandTestCase(DjangoGoApplicationTestCase):

    def setUp(self):
        super(GoSendAppWorkerCommandTestCase, self).setUp()
        self.setup_riak_fixtures()
        self.account_key = self.user.get_profile().user_account

        self.command = go_send_app_worker_command.Command()
        self.command.sender_class = DummyMessageSender
        self.command.allowed_commands = ['good_command']
        self.command.stdout = StringIO()
        self.command.stderr = StringIO()

    def test_invalid_command(self):
        self.assertRaises(CommandError, self.command.handle, 'worker-name',
            'bad_command', 'key=1', 'key=2')

    def test_reconcile_cache_invalid_user(self):
        self.assertRaises(CommandError, self.command.handle, 'worker-name',
            'reconcile_command', 'account_key=foo', 'conversation_key=bar')

    def test_reconcile_cache_invalid_conversation(self):
        self.assertRaises(CommandError, self.command.handle, 'worker-name',
            'reconcile_command', 'account_key=%s' % self.account_key,
            'conversation_key=bar')

    def test_reconcile_cache(self):
        self.command.handle('worker-name', 'reconcile_cache',
            'account_key=%s' % (self.account_key,),
            'conversation_key=%s' % (self.conv_key,))
        self.assertEqual(self.command.stderr.getvalue(), '')
        self.assertEqual(self.command.stdout.getvalue(), '')
        [cmd] = self.command.sender.outbox
        self.assertEqual(cmd['worker_name'], 'worker-name')
        self.assertEqual(cmd['command'], 'reconcile_cache')
        self.assertEqual(cmd['args'], [])
        self.assertEqual(cmd['kwargs'], {
            'user_account_key': self.account_key,
            'conversation_key': self.conv_key,
        })
