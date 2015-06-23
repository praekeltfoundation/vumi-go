from optparse import make_option

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model

from go.base.utils import vumi_api, vumi_api_for_user


def get_user_by_email(email):
    user_model = get_user_model()
    try:
        user = user_model.objects.get(email=email)
    except user_model.DoesNotExist, e:
        raise CommandError(e)
    return user


def get_user_by_account_key(account_key):
    user_model = get_user_model()
    try:
        user = user_model.objects.get(userprofile__user_account=account_key)
    except user_model.DoesNotExist:
        raise CommandError("Account %r does not exist" % (account_key,))
    return user


def get_users():
    user_model = get_user_model()
    return user_model.objects.all().order_by('date_joined')


def user_details_as_string(user):
    profile = user.get_profile()
    return u'%s %s <%s> [%s]' % (
        user.first_name,
        user.last_name,
        user.email,
        profile.user_account)


def make_command_opt_str(command_name):
    return '--%s' % (command_name.replace('_', '-'),)


def make_command_option(command_name, **kw):
    opt_str = make_command_opt_str(command_name)
    return make_option(
        opt_str, dest='command', action='append_const', const=command_name,
        **kw)


def make_email_option():
    return make_option(
        '--email-address', dest='email_address',
        help='Email address for the Vumi Go user')


class BaseGoCommand(BaseCommand):
    def list_commands(self):
        return [opt.const for opt in self.option_list
                if opt.action == 'append_const' and opt.dest == 'command']

    def mk_all_user_apis(self):
        apis = [(user, vumi_api_for_user(user)) for user in get_users()]
        apis.sort(key=lambda u: u[0].email)
        return apis

    def mk_user_api(self, email_address=None, options=None):
        if email_address is None and options is None:
            raise ValueError("email_address or options is required")
        if email_address is None:
            if options.get('email_address', None) is None:
                raise CommandError("--email-address must be specified")
            email_address = options.get('email_address')
        user = get_user_by_email(email_address)
        user_api = vumi_api_for_user(user)
        return user, user_api

    def mk_vumi_api(self):
        return vumi_api()

    def handle(self, *args, **options):
        self.options = options
        self.vumi_api = self.mk_vumi_api()
        return self.dispatch_command(*args, **options)

    def dispatch_command(self, *args, **options):
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


class BaseGoAccountCommand(BaseGoCommand):
    option_list = BaseGoCommand.option_list + (
        make_email_option(),
    )

    def handle(self, *args, **options):
        self.user, self.user_api = self.mk_user_api(options=options)
        return super(BaseGoAccountCommand, self).handle(*args, **options)
