from optparse import make_option

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User

from go.base.utils import vumi_api_for_user


class Command(BaseCommand):
    help = "Enable or disable metrics for a Vumi Go user"

    LOCAL_OPTIONS = [
        make_option('--email-address',
            dest='email-address',
            help='Email address for the Vumi Go user'),
        make_option('--enable',
            dest='enable',
            action='store_true',
            default=False,
            help='Give access to this application'),
        make_option('--disable',
            dest='disable',
            action='store_true',
            default=False,
            help='Revoke access to this application'),
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

        self.handle_validated(*args, **options)

    def handle_validated(self, *args, **options):
        try:
            email_address = options['email-address']
            enable = options['enable']
            disable = options['disable']

            if (enable and disable) or not (enable or disable):
                raise CommandError(
                    'Please specify either --enable or --disable.')

            user = User.objects.get(username=email_address)
            user_api = vumi_api_for_user(user)
            user_account_key = user_api.user_account_key
            redis = user_api.api.redis

            if enable:
                redis.sadd('metrics_accounts', user_account_key)
            elif disable:
                redis.srem('metrics_accounts', user_account_key)

        except User.DoesNotExist, e:
            raise CommandError(e)
