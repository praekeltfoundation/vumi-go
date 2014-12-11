from datetime import datetime
from optparse import make_option

from go.billing.models import Account
from go.billing.tasks import month_range, archive_transactions
from go.base.command_utils import BaseGoCommand, get_user_by_email


class Command(BaseGoCommand):
    help = (
        "Archive transactions for an account to S3 for the specified months.")

    option_list = BaseGoCommand.option_list + (
        make_option(
            '--email-address', dest='email_address',
            help="Email address of the account to archive transactions for."),
        make_option(
            '--month', dest='months', action='append',
            help="Month to generate statements for in the form YYYY-MM, "
            "e.g. 2014-01. Multiple may be specified."),
        make_option(
            '--delete', dest='delete', action="store_true", default=False,
            help=("Delete the transactions after uploading the archive."
                  " Default: FALSE.")),
    )

    def handle(self, *args, **opts):
        user = get_user_by_email(opts['email_address'])
        account_number = user.get_profile().user_account
        account = Account.objects.get(account_number=account_number)

        delete = opts['delete']
        months = [datetime.strptime(m, '%Y-%m') for m in opts['months']]

        self.stdout.write(
            "Archiving transactions for account %s..."
            % (opts['email_address'],))

        for month in months:
            from_date, to_date = month_range(0, month)

            archive = archive_transactions(
                account.id, from_date, to_date, delete=delete)

            self.stdout.write(
                "Archiving transactions that occured in %s..."
                % (datetime.strftime(month, '%Y-%m'),))

            self.stdout.write("Archived to S3 as %s." % (archive.filename,))
            self.stdout.write("Archive status is: %s." % (archive.status,))
            self.stdout.write("")
