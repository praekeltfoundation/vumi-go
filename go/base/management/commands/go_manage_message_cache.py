from optparse import make_option

from go.base.command_utils import (
    BaseGoCommand, make_command_option,
    user_details_as_string)


class Command(BaseGoCommand):
    help = "Manage the message cache."

    option_list = BaseGoCommand.option_list + (
        make_command_option(
            'rebuild', help='Rebuild the message cache.'),
        make_option(
            '--email-address', dest='email_address',
            help="Act on the given user's batches."),
        make_option('--batch-keys-file',
                    dest='batch_keys_file',
                    help='Act on all batches listed in this file.'),
        make_option('--conversation-key',
                    dest='conversation_key',
                    help='Act on the given conversation.'),
        make_option('--active-conversations',
                    dest='active_conversations',
                    action='store_true', default=False,
                    help='Act on all active conversations.'),
        make_option('--archived-conversations',
                    dest='archived_conversations',
                    action='store_true', default=False,
                    help='Act on all archived conversations.'),
        make_option('--router-key',
                    dest='router_key',
                    help='Act on the given router.'),
        make_option('--active-routers',
                    dest='active_routers',
                    action='store_true', default=False,
                    help='Act on all active routers.'),
        make_option('--archived-routers',
                    dest='archived_routers',
                    action='store_true', default=False,
                    help='Act on all archived routers.'),
        make_option('--dry-run',
                    dest='dry_run',
                    action='store_true', default=False,
                    help='Just pretend to act.'),
    )

    def _get_user_apis(self):
        if self.options.get("email_address"):
            return [self.mk_user_api(self.options["email_address"])]
        return self.mk_all_user_apis()

    def _apply_to_batches(self, func, batches, dry_run):
        for batch_id in sorted(batches):
            self.stdout.write("  Performing %s on batch %s ...\n" % (
                func.__name__, batch_id))
            if not dry_run:
                func(batch_id)
        self.stdout.write("done.\n")

    def _get_batches(self, user_api):
        batches = set()
        if self.options.get('conversation_key'):
            conv = user_api.get_conversation(self.options['conversation_key'])
            batches.add(conv.batch.key)
        if self.options.get('active_conversations'):
            batches.update(
                conv.batch.key for conv in user_api.active_conversations())
        if self.options.get('archived_conversations'):
            batches.update(
                conv.batch.key for conv in user_api.archived_conversations())
        if self.options.get('router_key'):
            conv = user_api.get_router(self.options['router_key'])
            batches.add(conv.batch.key)
        if self.options.get('active_routers'):
            batches.update(
                conv.batch.key for conv in user_api.active_routers())
        if self.options.get('archived_routers'):
            batches.update(
                conv.batch.key for conv in user_api.archived_routers())
        return list(batches)

    def _apply_to_batches_from_file(self, func, dry_run):
        batch_keys_file = self.options.get('batch_keys_file')
        if batch_keys_file:
            batches = []
            with open(batch_keys_file, 'r') as keys_file:
                for line in keys_file:
                    key = line.strip()
                    if key:
                        batches.append(key)
            self.stdout.write("Processing file %s ...\n" % (batch_keys_file))
            self._apply_to_batches(func, batches, dry_run)

    def _apply_to_accounts(self, func, dry_run):
        for user, user_api in self._get_user_apis():
            batches = self._get_batches(user_api)
            if not batches:
                continue
            self.stdout.write(
                "Processing account %s ...\n" % user_details_as_string(user))
            self._apply_to_batches(func, batches, dry_run)

    def _apply_command(self, func, dry_run=None):
        if dry_run is None:
            dry_run = self.options.get('dry_run')

        self._apply_to_batches_from_file(func, dry_run)
        self._apply_to_accounts(func, dry_run)

    def handle_command_rebuild(self, *args, **options):
        def rebuild(batch_id):
            self.mk_vumi_api().mdb.reconcile_cache(batch_id)

        self._apply_command(rebuild)
