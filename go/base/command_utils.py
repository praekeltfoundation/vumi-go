from optparse import make_option

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model

from go.base.utils import vumi_api_for_user


def make_command_opt_str(command_name):
    return '--%s' % (command_name.replace('_', '-'),)


def make_command_option(command_name, **kw):
    opt_str = make_command_opt_str(command_name)
    return make_option(
        opt_str, dest='command', action='append_const', const=command_name,
        **kw)


class BaseGoAccountCommand(BaseCommand):
    option_list = BaseCommand.option_list + (
        make_option('--email-address',
                    dest='email_address',
                    help='Email address for the Vumi Go user'),
    )

    def list_commands(self):
        return [opt.const for opt in self.option_list
                if opt.action == 'append_const' and opt.dest == 'command']

    def handle(self, *args, **options):
        user_model = get_user_model()
        if 'email_address' not in options:
            raise CommandError("--email-address must be specified")
        try:
            self.user = user_model.objects.get(email=options['email_address'])
        except user_model.DoesNotExist, e:
            raise CommandError(e)

        self.user_api = vumi_api_for_user(self.user)

        commands = options.get('command', [])
        if not commands:
            return self.handle_no_command(*args, **options)
        if len(commands) > 1:
            raise CommandError(
                "Multiple command options provided, only one allowed: %s" % (
                    ' '.join(make_command_opt_str(cmd) for cmd in commands)))
        [command] = commands
        return getattr(self, 'handle_command_%s' % command)(*args, **options)

    def handle_no_command(self, *args, **options):
        raise CommandError(
            'Please specify one of the following actions: %s' % (
                ' '.join(make_command_opt_str(cmd)
                         for cmd in self.list_commands())))
