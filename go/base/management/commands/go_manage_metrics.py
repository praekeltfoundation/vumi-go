from go.base.command_utils import (
    BaseGoCommand, make_command_option, make_email_option,
    get_user_by_account_key, user_details_as_string)


class Command(BaseGoCommand):
    # TODO Use riak instead of redis for maintaining the list of accounts
    # for which metric collection should be disabled

    encoding = 'utf-8'

    help = "Disable or re-enable metric collection for a Vumi Go user"

    option_list = BaseGoCommand.option_list + (
        make_email_option(),
        make_command_option('list',
            help='List the Vumi Go user accounts that currently have '
                 'metric collection disabled'),
        make_command_option('enable',
            help='Enable metric collection for the Vumi Go user'),
        make_command_option('disable',
            help='Disable metric collection for the Vumi Go user'),
    )

    def handle_command_enable(self, *args, **options):
        _user, user_api = self.mk_user_api(options=options)
        user_account_key = user_api.user_account_key
        self.vumi_api.redis.srem('disabled_metrics_accounts', user_account_key)

    def handle_command_disable(self, *args, **options):
        _user, user_api = self.mk_user_api(options=options)
        user_account_key = user_api.user_account_key
        self.vumi_api.redis.sadd('disabled_metrics_accounts', user_account_key)

    def handle_command_list(self, *args, **options):
        acc_keys = self.vumi_api.redis.smembers('disabled_metrics_accounts')

        if not acc_keys:
            self.stderr.write('No accounts have metric collection disabled.\n')
        else:
            for i, acc_key in enumerate(acc_keys):
                user = get_user_by_account_key(acc_key)
                output = u"%s. %s\n" % (i, user_details_as_string(user))
                self.stdout.write(output.encode(self.encoding))
