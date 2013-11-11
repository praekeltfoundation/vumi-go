from optparse import make_option

from django.core.management.base import BaseCommand, CommandError

from go.base.utils import vumi_api_for_user
from go.base.command_utils import get_user_by_email


class Command(BaseCommand):
    help = "Disable or re-enable metric collection for a Vumi Go user"

    LOCAL_OPTIONS = [
        make_option('--email-address',
            dest='email-address',
            help='Email address for the Vumi Go user'),
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
    ]
    option_list = BaseCommand.option_list + tuple(LOCAL_OPTIONS)

    def handle(self, *args, **options):
        options = options.copy()
        for opt in self.LOCAL_OPTIONS:
            if options.get(opt.dest) is None:
                value = raw_input("%s: " % (opt.help,))
                if value:
                    options[opt.dest] = value
                else:
                    raise CommandError('Please provide %s:' % (opt.dest,))

        enable = options['enable']
        disable = options['disable']

        if (enable and disable) or not (enable or disable):
            raise CommandError(
                'Please specify either --enable or --disable.')

        self.handle_validated(*args, **options)

    def handle_validated(self, *args, **options):
        email_address = options['email-address']
        enable = options['enable']
        disable = options['disable']

        user = get_user_by_email(email_address)
        user_api = vumi_api_for_user(user)
        user_account_key = user_api.user_account_key

        # TODO use riak instead of riak for this command
        redis = user_api.api.redis

        if enable:
            redis.srem('disabled_metrics_accounts', user_account_key)
        elif disable:
            redis.sadd('disabled_metrics_accounts', user_account_key)
