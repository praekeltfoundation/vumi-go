from django.core.management.base import BaseCommand
from django.db.models import Q
from django.contrib.auth.models import User


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

    def handle(self, *usernames, **options):
        users = User.objects.all().order_by('date_joined')
        if usernames:
            or_statements = [Q(username__regex=un) for un in usernames]
            or_query = reduce(lambda x, y: x | y, or_statements)
            users = users.filter(or_query)
        if not users.exists():
            self.stderr.write('No accounts found.\n')
        for index, user in enumerate(users):
            profile = user.get_profile()
            self.stdout.write('%s. %s <%s> [%s]\n' % (index, profile,
                user.username, profile.user_account))
