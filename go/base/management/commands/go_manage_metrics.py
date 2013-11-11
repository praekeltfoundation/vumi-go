from optparse import make_option

from django.core.management.base import BaseCommand, CommandError

from go.base.utils import vumi_api, vumi_api_for_user
from go.base.command_utils import (
    get_user_by_email, get_user_by_account_key, user_details_as_string)


class Command(BaseCommand):
    encoding = 'utf-8'

    help = "Disable or re-enable metric collection for a Vumi Go user"

    LOCAL_OPTIONS = dict((opt.dest, opt) for opt in [
        make_option('--email-address',
            dest='email-address',
            help='Email address for the Vumi Go user'),
        make_option('--list',
            dest='list',
            action='store_true',
            default=False,
            help='List the Vumi Go user accounts that currently have '
                 'metric collection disabled'),
        make_option('--enable',
            dest='enable',
            action='store_true',
            default=False,
            help='Enable metric collection for the Vumi Go user'),
        make_option('--disable',
            dest='disable',
            action='store_true',
            default=False,
            help='Disable metric collection for the Vumi Go user'),
    ])

    option_list = BaseCommand.option_list + tuple(LOCAL_OPTIONS.values())

    def handle(self, *args, **options):
        action = self.get_action(options)

        if action == 'list':
            self.list_users()
        else:
            email_addr = (
                options.get('email-address') or
                self.ask_for_option('email-address'))

            if action == 'enable':
                self.enable_metrics(email_addr)
            elif action == 'disable':
                self.disable_metrics(email_addr)

    def ask_for_option(self, name):
        opt = self.LOCAL_OPTIONS[name]
        value = raw_input("%s: " % (opt.help,))
        if value:
            return value
        else:
            raise CommandError('Please provide %s:' % (opt.dest,))

    def get_action(self, options):
        actions = [
            name for name in ['enable', 'disable', 'list']
            if options[name]]

        if len(actions) != 1:
            raise CommandError(
                'Please specify either --list, --enable or --disable.')

        return actions[0]

    def enable_metrics(self, email_addr):
        user = get_user_by_email(email_addr)
        user_api = vumi_api_for_user(user)
        user_account_key = user_api.user_account_key
        redis = user_api.api.redis
        redis.srem('disabled_metrics_accounts', user_account_key)

    def disable_metrics(self, email_addr):
        user = get_user_by_email(email_addr)
        user_api = vumi_api_for_user(user)
        user_account_key = user_api.user_account_key
        redis = user_api.api.redis
        redis.sadd('disabled_metrics_accounts', user_account_key)

    def list_users(self):
        api = vumi_api()
        acc_keys = api.redis.smembers('disabled_metrics_accounts')

        if not acc_keys:
            self.stderr.write('No accounts have metric collection disabled.\n')
        else:
            for i, acc_key in enumerate(acc_keys):
                user = get_user_by_account_key(acc_key)
                output = u"%s. %s\n" % (i, user_details_as_string(user))
                self.stdout.write(output.encode(self.encoding))
