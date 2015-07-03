from optparse import make_option
import textwrap

from django.db.models import Q

from vumi.persist.model import ModelMigrationError

from go.base.command_utils import BaseGoCommand, get_users


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

    def get_conversation(self, user_api, conv_key):
        """Loads the conversation model object for this key.

        By default, this uses `user_api.get_wrapped_conversation()`, but some
        migrations may want to return something different. For example, an
        older model version.

        This may return something other than a conversation object (to signal
        that the object couldn't be loaded and we want to ignore it), but
        `applies_to()` should always return `False` for these.
        """
        return user_api.get_wrapped_conversation(conv_key)

    def run(self, user_api, conv):
        if not self._dry_run:
            self.migrate(user_api, conv)

    def applies_to(self, user_api, conv):
        """Whether this migration applies to the given conversation.

        Should return True if this conversation requires migrating, False
        otherwise.
        """
        raise NotImplementedError("Migration %s is missing an implementation"
                                  " of .applies_to()." % (self.name,))

    def migrate(self, user_api, conv):
        """Perform the migration."""
        raise NotImplementedError("Migration %s not implemented."
                                  % (self.name,))


class UpdateModels(Migration):
    name = "migrate-models"
    help_text = (
        "Load and re-save all conversations, triggering any pending model"
        " migrators in the process.")

    def applies_to(self, user_api, conv):
        return True

    def migrate(self, user_api, conv):
        if conv.was_migrated:
            conv.save()


class FixBatches(Migration):
    name = "fix-batches"
    help_text = (
        "Look for version 2 (or older) conversations which don't have exactly"
        " one batch. Create a new batch for such conversations and copy the"
        " messages from all conversation batches (if any) to the new batch.")

    def get_conversation(self, user_api, conv_key):
        """Load v2 conversations.

        This migration fixes a problem that prevents us from upgrading a v2
        conversation to v3.
        """
        from go.vumitools.conversation.old_models import ConversationV2
        v2_model = user_api.conversation_store.manager.proxy(ConversationV2)
        try:
            return v2_model.load(conv_key)
        except ModelMigrationError as e:
            if e.message.startswith(
                    'No migrators defined for ConversationV2 version '):
                return None
            raise

    def applies_to(self, user_api, conv):
        if conv is None:
            # We couldn't load the conversation, so we can't migrate it.
            return False
        return len(conv.batches.keys()) != 1

    def _process_pages(self, index_page, batch_id, get_message, add_message):
        while index_page is not None:
            for key in index_page:
                add_message(get_message(key), batch_ids=[batch_id])
            index_page = index_page.next_page()

    def _copy_msgs(self, FIXME_mdb, old_batch, new_batch):
        self._process_pages(
            FIXME_mdb.batch_outbound_keys_page(old_batch), new_batch,
            FIXME_mdb.get_outbound_message, FIXME_mdb.add_outbound_message)
        self._process_pages(
            FIXME_mdb.batch_inbound_keys_page(old_batch), new_batch,
            FIXME_mdb.get_inbound_message, FIXME_mdb.add_inbound_message)

    def migrate(self, user_api, conv):
        conv_batches = conv.batches.keys()
        new_batch = user_api.api.get_batch_manager().batch_start()
        for batch in conv_batches:
            self._copy_msgs(user_api.api.FIXME_mdb, batch, new_batch)
        conv.batches.clear()
        conv.batches.add_key(new_batch)
        conv.save()


class SplitBatches(Migration):
    name = "split-batches"
    help_text = (
        "Look for conversations which have a batch with a tag. Create a new"
        " batch for such conversations and copy the messages from all"
        " conversation batches to the new batch.")

    def applies_to(self, user_api, conv):
        FIXME_mdb = user_api.api.FIXME_mdb
        tag_keys = FIXME_mdb.current_tags.index_keys('current_batch', conv.batch.key)
        if tag_keys:
            return True
        return False

    def _process_pages(self, index_page, batch_id, get_message, add_message):
        while index_page is not None:
            for key in index_page:
                add_message(get_message(key), batch_ids=[batch_id])
            index_page = index_page.next_page()

    def _copy_msgs(self, FIXME_mdb, old_batch, new_batch):
        self._process_pages(
            FIXME_mdb.batch_outbound_keys_page(old_batch), new_batch,
            FIXME_mdb.get_outbound_message, FIXME_mdb.add_outbound_message)
        self._process_pages(
            FIXME_mdb.batch_inbound_keys_page(old_batch), new_batch,
            FIXME_mdb.get_inbound_message, FIXME_mdb.add_inbound_message)

    def migrate(self, user_api, conv):
        old_batch = conv.batch.key
        new_batch = user_api.api.get_batch_manager().batch_start()
        self._copy_msgs(user_api.api.FIXME_mdb, old_batch, new_batch)
        conv.batch.key = new_batch
        conv.save()


class FixJsboxEndpoint(Migration):
    name = "fix-jsbox-endpoints"
    help_text = "Set extra endpoints for conversations of type jsbox."

    def applies_to(self, user_api, conv):
        return conv.conversation_type == u'jsbox'

    def _extra_endpoints(self, conv):
        # import definition locally so migrators don't rely on
        # jsbox conversation
        from go.apps.jsbox.definition import ConversationDefinition
        conv_def = ConversationDefinition(conv)
        endpoints = list(conv_def.extra_static_endpoints)
        for endpoint in conv_def.configured_endpoints(conv.config):
            if (endpoint != 'default') and (endpoint not in endpoints):
                endpoints.append(endpoint)
        return endpoints

    def migrate(self, user_api, conv):
        conv.c.extra_endpoints = self._extra_endpoints(conv)
        conv.save()


class Command(BaseGoCommand):
    help = """
    Find and migrate conversations for known accounts in Vumi Go.
    Allows for optional searching on the email.

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
    option_list = BaseGoCommand.option_list + (
        make_option('-l', '--list', action='store_true',
                    dest='list_migrations',
                    default=False, help='List available migrations.'),
        make_option('-m', '--migrate', dest='migration_name',
                    default=None, help='Actually perform migrations.'),
        make_option('-d', '--dry-run', action='store_true', dest='dry_run',
                    default=False, help='Perform a dry run only.'),
        )

    def outln(self, msg, ending='\n'):
        self.stdout.write(msg.encode(self.encoding) + ending)

    def find_accounts(self, *usernames):
        users = get_users()
        if usernames:
            or_statements = [Q(email__regex=un) for un in usernames]
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
        user_api = self.user_api_for_user(user)
        all_keys = user_api.conversation_store.list_conversations()
        conversations = []
        for conv_key in all_keys:
            try:
                conv = migrator.get_conversation(user_api, conv_key)
            except ModelMigrationError as e:
                self.stderr.write("Error migrating conversation %s: %s" % (
                    conv_key, e.message))
                continue
            if migrator.applies_to(user_api, conv):
                conversations.append(conv)
        self.outln(
            u'%s %s <%s> [%s]\n  Migrating %d of %d conversations ...' % (
                user.first_name, user.last_name, user.email,
                user_api.user_account_key, len(conversations), len(all_keys)))
        for conv in conversations:
            self.outln(u'    Migrating conversation: %s [%s] ...'
                       % (conv.key, conv.name), ending='')
            migrator.run(user_api, conv)
            self.outln(u' done.')

    def handle_no_command(self, *usernames, **options):
        if options['list_migrations']:
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
