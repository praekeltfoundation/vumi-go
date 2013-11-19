from django.core.management.base import BaseCommand
from django.db.models import Q

from go.base.command_utils import get_users, user_details_as_string


class Command(BaseCommand):
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

    def handle(self, *usernames, **options):
        users = get_users()
        if usernames:
            or_statements = [Q(email__regex=un) for un in usernames]
            or_query = reduce(lambda x, y: x | y, or_statements)
            users = users.filter(or_query)
        if not users.exists():
            self.stderr.write('No accounts found.\n')
        for index, user in enumerate(users):
            output = u"%s. %s\n" % (index, user_details_as_string(user))
            self.stdout.write(output.encode(self.encoding))
