# -*- coding: utf-8 -*-
from StringIO import StringIO

from go.vumitools.tests.helpers import djangotest_imports

with djangotest_imports(globals()):
    from django.core.management.base import CommandError

    from go.base.management.commands import go_send_app_worker_command
    from go.base.tests.helpers import GoDjangoTestCase, DjangoVumiApiHelper


class TestGoSendAppWorkerCommand(GoDjangoTestCase):

    def setUp(self):
        self.vumi_helper = self.add_helper(DjangoVumiApiHelper())
        self.user_helper = self.vumi_helper.make_django_user()

        self.command = go_send_app_worker_command.Command()
        self.command.stdout = StringIO()
        self.command.stderr = StringIO()
        self.command.allowed_commands = ['good_command']

    def test_invalid_command(self):
        self.assertRaisesRegexp(CommandError, 'Unknown command bad_command',
            self.command.handle, 'worker-name', 'bad_command',
            'key=1', 'key=2')

    def test_reconcile_cache_invalid_user(self):
        self.assertRaisesRegexp(CommandError, "Account 'foo' does not exist",
            self.command.handle, 'worker-name', 'reconcile_cache',
            'account_key=foo', 'conversation_key=bar')

    def test_reconcile_cache_invalid_conversation(self):
        self.assertRaisesRegexp(
            CommandError, 'Conversation does not exist', self.command.handle,
            'worker-name', 'reconcile_cache',
            'account_key=%s' % self.user_helper.account_key,
            'conversation_key=bar')

    def test_reconcile_cache(self):
        conv = self.user_helper.create_conversation(u'bulk_message')
        self.command.handle(
            'worker-name', 'reconcile_cache',
            'account_key=%s' % (self.user_helper.account_key,),
            'conversation_key=%s' % (conv.key,))
        self.assertEqual(self.command.stderr.getvalue(), '')
        self.assertEqual(self.command.stdout.getvalue(), '')
        [cmd] = self.vumi_helper.amqp_connection.get_commands()
        self.assertEqual(cmd['worker_name'], 'worker-name')
        self.assertEqual(cmd['command'], 'reconcile_cache')
        self.assertEqual(cmd['args'], [])
        self.assertEqual(cmd['kwargs'], {
            'user_account_key': self.user_helper.account_key,
            'conversation_key': conv.key,
        })
