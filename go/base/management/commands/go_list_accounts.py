from optparse import make_option

from django.db.models import Q

from go.base.command_utils import (
    BaseGoCommand, get_users, user_details_as_string)


class Command(BaseGoCommand):
    help = """
    List known accounts on Vumi Go. Allows for optional searching on the
    username.

    Usage:

    ./go-admin.sh go_list_accounts:

        Lists all known accounts ordered by `date_joined`

    ./go-admin.sh go_list_accounts <optional regex>:

        Lists all known accounts order_by `date_joined` matching
        the given regular expression.

    """
    args = "[optional username regex]"
    encoding = 'utf-8'

    option_list = BaseGoCommand.option_list + (
        make_option(
            '--show-pools', dest='show-pools', default=False,
            action='store_true',
            help="Show tag pool permissions in account listing"),
        make_option(
            '--show-tags', dest='show-tags', default=False,
            action='store_true',
            help="Show owned tags in account listing"),
    )

    def handle_no_command(self, *usernames, **options):
        users = get_users()
        if usernames:
            or_statements = [Q(email__regex=un) for un in usernames]
            or_query = reduce(lambda x, y: x | y, or_statements)
            users = users.filter(or_query)
        if not users.exists():
            self.stderr.write('No accounts found.\n')
        for index, user in enumerate(users):
            self.print_account(index, user, options)

    def print_account(self, index, user, options):
        output = u"%s. %s\n" % (index, user_details_as_string(user))
        self.stdout.write(output.encode(self.encoding))
        user_api = self.user_api_for_user(user)
        if options.get('show-pools'):
            self.stdout.write("  Pools:\n")
            user_account = user_api.get_user_account()
            for tp_bunch in user_account.tagpools.load_all_bunches():
                for tp in tp_bunch:
                    self.stdout.write(
                        "    %r (max-keys: %s)" % (tp.tagpool, tp.max_keys))
        if options.get('show-tags'):
            self.stdout.write("  Tags:\n")
            for channel in user_api.active_channels():
                self.stdout.write(
                    "    (%r, %r)\n" % (channel.tagpool, channel.tag))
