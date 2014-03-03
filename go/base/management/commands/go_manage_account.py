from optparse import make_option

from go.base.command_utils import (
    BaseGoCommand, CommandError, make_command_option,
    user_details_as_string, get_user_by_account_key)
from go.billing.models import Account


class Command(BaseGoCommand):
    help = "Manage Go accounts."

    option_list = BaseGoCommand.option_list + (
        make_command_option(
            'create_billing_account',
            help=(
                "Create a billing account table entry for the user if"
                "there isn't an entry already.")),
        make_option(
            '--email-address', dest='email_address',
            help="Act on the given user."),
        make_option(
            '--all',
            dest='all_accounts',
            action='store_true', default=False,
            help='Act on all accounts.'),
        make_option('--dry-run',
            dest='dry_run',
            action='store_true', default=False,
            help='Just pretend to act.'),
    )

    def _get_user_apis(self):
        if self.options.get("email_address"):
            return [self.mk_user_api(self.options["email_address"])]
        if self.options.get("all_accounts"):
            return self.mk_all_user_apis()
        raise CommandError(
            "Please specify either --email-address or --all-users")

    def _apply_to_accounts(self, func, dry_run=None):
        if dry_run is None:
            dry_run = self.options.get('dry_run')

        for user, user_api in self._get_user_apis():
            self.stdout.write(
                "Performing %s on account %s ...\n" % (
                    func.__name__, user_details_as_string(user)
                ))
            if not dry_run:
                func(user_api)
            self.stdout.write("done.\n")

    def handle_command_create_billing_account(self, *args, **options):
        def create_billing_account(user_api):
            account_key = user_api.user_account_key
            user = get_user_by_account_key(account_key)
            _, created = Account.objects.get_or_create(
                user=user, account_number=account_key)
            if created:
                self.stdout.write(
                    "  Created billing account.\n")
            else:
                self.stdout.write(
                    "  Billing account already exists.\n")

        self._apply_to_accounts(create_billing_account)
