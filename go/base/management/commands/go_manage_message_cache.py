from optparse import make_option

from go.base.command_utils import (
    BaseGoCommand, make_command_option,
    user_details_as_string)


class Command(BaseGoCommand):
    help = "Manage the message cache."

    option_list = BaseGoCommand.option_list + (
        make_command_option(
            'reconcile', help='Reconcile the message cache.'),
        make_command_option(
            'switch_to_counters', help='Switch cache to counters.'),
        make_option(
            '--email-address', dest='email_address',
            help="Act on the given user's batches."),
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
        make_option('--dry-run',
                    dest='dry_run',
                    action='store_true', default=False,
                    help='Just pretend to act.'),
    )

    def _get_user_apis(self):
        if self.options.get("email_address"):
            return [self.mk_user_api(self.options["email_address"])]
        return self.mk_all_user_apis()

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
                conv.batch.key for conv in user_api.finished_conversations())
        return list(batches)

    def _apply_to_batches(self, func, dry_run=None):
        if dry_run is None:
            dry_run = self.options.get('dry_run')

        for user, user_api in self._get_user_apis():
            batches = self._get_batches(user_api)
            if not batches:
                continue
            self.stdout.write(
                "Processing account %s ...\n" % user_details_as_string(user))
            for batch_id in sorted(batches):
                self.stdout.write(
                    "  Performing %s on batch %s ...\n"
                    % (func.__name__, batch_id))
                if not dry_run:
                    func(user_api, batch_id)
            self.stdout.write("done.\n")

    def handle_command_reconcile(self, *args, **options):
        def reconcile(user_api, batch_id):
            user_api.api.mdb.reconcile_cache(batch_id)

        self._apply_to_batches(reconcile)

    def handle_command_switch_to_counters(self, *args, **options):
        def switch_to_counters(user_api, batch_id):
            user_api.api.mdb.cache.switch_to_counters(batch_id)

        self._apply_to_batches(switch_to_counters)
