import uuid
from optparse import make_option

from go.base.command_utils import BaseGoAccountCommand, CommandError


class Command(BaseGoAccountCommand):
    help = "Give a Vumi Go user access to a certain tagpool"

    LOCAL_OPTIONS = [
        make_option(
            '--tagpool',
            dest='tagpool',
            help='The tagpool to give access to'),
        make_option(
            '--max-keys',
            dest='max_keys',
            default=None,
            help='Maximum number of keys that can be acquired '
                 '(0 == Unlimited)'),
        make_option(
            '--update',
            dest='update',
            action='store_true',
            default=False,
            help='Update an existing permission with a new max-keys value'),
        make_option(
            '--remove',
            dest='remove',
            action='store_true',
            default=False,
            help='Remove an existing permission'),
    ]
    option_list = BaseGoAccountCommand.option_list + tuple(LOCAL_OPTIONS)

    def handle_no_command(self, *args, **options):
        tagpool = unicode(options['tagpool'])

        account = self.user_api.get_user_account()
        existing_perms = []
        for permissions in account.tagpools.load_all_bunches():
            existing_perms.extend([
                p for p in permissions if p.tagpool == tagpool])

        if len(existing_perms) > 1:
            raise CommandError(
                '%s permissions specified for the same tagpool. Please fix'
                ' manually' % (len(existing_perms),))

        if options['update']:
            self.process_update_permission(
                account, tagpool, existing_perms, options)
        elif options['remove']:
            self.process_remove_permission(
                account, tagpool, existing_perms, options)
        else:
            self.process_create_permission(
                account, tagpool, existing_perms, options)

    def process_update_permission(self, account, tagpool, perms, options):
        if not perms:
            raise CommandError(
                'Could not update permission. Tagpool permission not found.')
        if not options['max_keys']:
            raise CommandError(
                'Updating a permission requires setting the max_keys options.')
        max_keys = int(options['max_keys']) or None
        self.update_permission(perms[0], max_keys)

    def update_permission(self, tagpool_permission, max_keys):
        tagpool_permission.max_keys = max_keys
        tagpool_permission.save()

    def process_remove_permission(self, account, tagpool, perms, options):
        if not perms:
            raise CommandError(
                'Could not remove permission. Tagpool permission not found.')
        if options['max_keys'] is not None:
            raise CommandError(
                'The max-keys option is may not be set when when deleting a'
                ' permission.')
        self.remove_permission(perms[0])

    def remove_permission(self, tagpool_permission):
        tagpool_permission.delete()

    def process_create_permission(self, account, tagpool, perms, options):
        if perms:
            raise CommandError(
                'Could not create permission. Tagpool permission already'
                ' exists. Use --update to update the value of max-keys.')
        if not options['max_keys']:
            raise CommandError(
                'Creating a permission requires setting the max_keys options.')
        max_keys = int(options['max_keys']) or None
        self.create_permission(account, tagpool, max_keys)

    def create_permission(self, account, tagpool, max_keys):
        api = self.user_api.api
        if tagpool not in api.tpm.list_pools():
            raise CommandError("Tagpool '%s' does not exist" % (tagpool,))

        permission = api.account_store.tag_permissions(
            uuid.uuid4().hex, tagpool=tagpool, max_keys=max_keys)
        permission.save()

        account.tagpools.add(permission)
        account.save()
