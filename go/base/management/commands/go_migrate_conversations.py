from optparse import make_option
import textwrap

from django.core.management.base import BaseCommand
from django.db.models import Q
from django.contrib.auth.models import User

from go.base.utils import vumi_api_for_user


class Migration(object):
    """Base class for migrations."""
    name = None

    def __init__(self, dry_run):
        self._dry_run = dry_run

    @classmethod
    def migrator_classes(cls):
        return cls.__subclasses__()

    @classmethod
    def migrator_class(cls, name):
        for migrator_cls in cls.migrator_classes():
            if migrator_cls.name == name:
                return migrator_cls
        return None

    def run(self, conv):
        if self._dry_run:
            self.migrate(conv)

    def applies_to(self, conv):
        """Whether this migration applies to the given conversation.

        Should return True if this conversation requires migrating, False
        otherwise.
        """
        return True

    def migrate(self, conv):
        """Perform the migration."""
        raise NotImplementedError("Migration %s not implemented."
                                  % (self.name,))


class UpdateModels(Migration):
    name = "migrate-models"
    help_text = (
        "Load and re-save all conversations, triggering an pending model"
        " migrators in the process.")

    def migrate(self, conv):
        conv.save()


class SeparateTagBatches(Migration):
    name = "separate-tag-batches"
    help_text = (
        "Look for active conversations which have a tag and where that tag's"
        " current batch is the same as the conversation's batch. Copy this"
        " this batch to a new batch and assign the new batch to the"
        " conversation.")

    def applies_to(self, conv):
        raise NotImplementedError("TODO: implement")

    def migrate(self, conv):
        raise NotImplementedError("TODO: implement")


class Command(BaseCommand):
    help = """
    Find and migrate conversations for known accounts in Vumi Go.
    Allows for optional searching on the username.

    Usage:

    ./go-admin.sh go_migrate_conversations --list

        List possible migrations.

    ./go-admin.sh go_migrate_conversations --migrate <migration-name>

        Perform the specified migration.

    ./go-admin.sh go_migrate_conversations --migrate <migration-name> --dry-run

        Perform a dry-run of the specified migration.

    ./go-admin.sh go_migrate_conversations --migrate <migration-name> [regex]

        As above, but only operate on accounts matching the given regex.
    """

    args = "[optional username regex]"
    encoding = 'utf-8'
    option_list = BaseCommand.option_list + (
        make_option('-l', '--list', action='store_true', dest='list',
                    default=False, help='List available migrations.'),
        make_option('-m', '--migrate', dest='migration_name',
                    default=None, help='Actually perform migrations.'),
        make_option('-d', '--dry-run', action='store_true', dest='dry_run',
                    default=False, help='Perform a dry run only.'),
        )

    def outln(self, msg, ending='\n'):
        self.stdout.write(msg.encode(self.encoding) + ending)

    def find_accounts(self, *usernames):
        users = User.objects.all().order_by('date_joined')
        if usernames:
            or_statements = [Q(username__regex=un) for un in usernames]
            or_query = reduce(lambda x, y: x | y, or_statements)
            users = users.filter(or_query)
        if not users.exists():
            self.stderr.write('No accounts found.\n')
        return users

    def handle_list(self):
        self.outln("Available migrations:")
        for migrator_cls in Migration.migrator_classes():
            self.outln("")
            self.outln("  %s:" % (migrator_cls.name,))
            self.outln("")
            for line in textwrap.wrap(migrator_cls.help_text, width=66):
                self.outln("    %s" % line)

    def get_migrator(self, migration_name, dry_run):
        migrator_cls = Migration.migrator_class(migration_name)
        if migrator_cls is None:
            return None
        return migrator_cls(dry_run)

    def handle_user(self, user, migrator):
        user_api = vumi_api_for_user(user)
        all_keys = user_api.conversation_store.list_conversations()
        conversations = [user_api.get_wrapped_conversation(k)
                         for k in all_keys]
        conversations = [c for c in conversations if migrator.applies_to(c)]
        self.outln(
            u'%s %s <%s> [%s]\n  Migrating %d of %d conversations ...' % (
            user.first_name, user.last_name, user.username,
            user_api.user_account_key, len(conversations), len(all_keys)))
        for conv in conversations:
            self.outln(u'    Migrating conversation: %s [%s] ...'
                       % (conv.key, conv.name), ending='')
            migrator.run(conv)
            self.outln(u' done.')

    def handle(self, *usernames, **options):
        if options['list']:
            self.handle_list()
            return
        migration_name = options['migration_name']
        if migration_name is None:
            self.stderr.write('Please specify a migration.\n')
            return
        migrator = self.get_migrator(migration_name, options['dry_run'])
        if migrator is None:
            self.stderr.write('Unknown migration %s.\n' % (migration_name,))
            return
        users = self.find_accounts(*usernames)
        for user in users:
            self.handle_user(user, migrator)
