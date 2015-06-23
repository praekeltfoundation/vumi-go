from optparse import make_option

from django.core.management.base import CommandError

from go.base.command_utils import BaseGoAccountCommand, make_command_option
from go.base.tests.helpers import GoAccountCommandTestCase


class DummyGoDjangoAccountCommand(BaseGoAccountCommand):
    option_list = BaseGoAccountCommand.option_list + (
        make_command_option('foo'),
        make_command_option('bar'),
        make_option('--opt', action='store', dest='opt'),
    )

    def handle_command_foo(self, *args, **options):
        self.stdout.write('foo\n')

    def handle_command_bar(self, *args, **options):
        self.stdout.write('bar: %s\n' % (options['opt'],))


class TestBaseGoAccountCommand(GoAccountCommandTestCase):
    def setUp(self):
        self.setup_command(DummyGoDjangoAccountCommand)

    def test_user_email_required(self):
        self.assertRaisesRegexp(
            CommandError, '--email-address must be specified',
            self.command.handle)
        self.assertRaisesRegexp(
            CommandError, '--email-address must be specified',
            self.command.handle, email_address=None)

    def test_user_account_must_exist(self):
        self.assertRaisesRegexp(
            CommandError, 'User matching query does not exist',
            self.command.handle, email_address='foo@bar')

    def test_too_many_commands(self):
        self.assert_command_error(
            'Multiple command options provided, only one allowed: --foo --bar',
            'foo', 'bar')

    def test_no_command_default(self):
        self.assert_command_error(
            'Please specify one of the following actions: --foo --bar')

    def test_no_command_override(self):
        def handle_no_command(*args, **options):
            self.command.stdout.write('no command\n')

        self.command.handle_no_command = handle_no_command
        self.assert_command_output('no command\n')

    def test_command_foo(self):
        self.assert_command_output('foo\n', 'foo')

    def test_command_bar(self):
        self.assert_command_output('bar: hi\n', 'bar', opt='hi')
