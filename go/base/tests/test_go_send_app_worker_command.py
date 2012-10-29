# -*- coding: utf-8 -*-
from StringIO import StringIO

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
        self.user = self.mk_django_user()

        self.command = go_send_app_worker_command.Command()
        self.command.sender_class = DummyMessageSender
        self.command.allowed_commands = ['good_command']
        self.command.stdout = StringIO()
        self.command.stderr = StringIO()

    def test_invalid_command(self):
        self.command.handle('worker-name', 'bad_command', 'key=1 key=2')
        self.assertEqual(self.command.stderr.getvalue(),
            'Unknown command bad_command')

    def test_valid_command(self):
        self.command.handle('worker-name', 'good_command', 'key=1 key=2')
        self.assertEqual(self.command.stderr.getvalue(), '')
        self.assertEqual(self.command.stdout.getvalue(), '')
        [cmd] = self.command.sender.outbox
        self.assertEqual(cmd['worker_name'], 'worker-name')
        self.assertEqual(cmd['command'], 'good_command')
        self.assertEqual(cmd['args'], [])
        self.assertEqual(cmd['kwargs'], {'key': '1', 'key': '2'})
