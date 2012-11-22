from optparse import make_option

from django.core.management.base import BaseCommand
from django.db.models import Q
from django.contrib.auth.models import User

from go.base.utils import vumi_api_for_user


class Command(BaseCommand):
    help = """
    Find and migrate conversations for known accounts in Vumi Go.
    Allows for optional searching on the username.

    Usage:

    ./go-admin.sh go_migrate_conversations:

        Migrate conversations for all known accounts.

    ./go-admin.sh go_migrate_conversations <optional regex>:

        Migrate conversations for all known accounts matching the given regular
        expression.

    """
    args = "[optional username regex]"
    encoding = 'utf-8'
    option_list = BaseCommand.option_list + (
        make_option('--migrate', action='store_true', dest='migrate',
                    default=False, help='Actually perform migrations.'),
        )

    def find_accounts(self, *usernames):
        users = User.objects.all().order_by('date_joined')
        if usernames:
            or_statements = [Q(username__regex=un) for un in usernames]
            or_query = reduce(lambda x, y: x | y, or_statements)
            users = users.filter(or_query)
        if not users.exists():
            self.stderr.write('No accounts found.\n')
        return users

    def handle_user(self, user, migrate):
        user_api = vumi_api_for_user(user)
        conversations = user_api.conversation_store.list_conversations()
        output = u'%s %s <%s> [%s]\n    Conversations: %s\n' % (
            user.first_name, user.last_name, user.username,
            user_api.user_account_key, len(conversations))
        self.stdout.write(output.encode(self.encoding))
        if migrate:
            for conv_key in conversations:
                conv = user_api.get_wrapped_conversation(conv_key)
                self.stdout.write(u'  Migrating conversation: %s [%s]\n' %
                    (conv.name, conv_key))
                conv.save()

    def handle(self, *usernames, **options):
        users = self.find_accounts(*usernames)
        for user in users:
            self.handle_user(user, options['migrate'])
