from datetime import datetime
from optparse import make_option

from go.billing.models import Statement, Account
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
        make_option(
            '--no-statement',
            dest='no_statement', action="store_true", default=False,
            help=("Allow transactions to be archived even if no equivalent "
                  "billing statement is found. Default: FALSE.")))

    def statement_exists(self, account, from_date, to_date):
        statements = Statement.objects.filter(
            account=account,
            from_date=from_date,
            to_date=to_date)

        return statements.exists()

    def missing_statement_months(self, account, months):
        return [
            m for m in months
            if not self.statement_exists(account, *month_range(0, m))]

    def archive_month_transactions(self, account, month, delete):
        from_date, to_date = month_range(0, month)

        self.stdout.write(
            "Archiving transactions that occured in %s..."
            % (datetime.strftime(month, '%Y-%m'),))

        archive = archive_transactions(
            account.id, from_date, to_date, delete=delete)

        self.stdout.write("Archived to S3 as %s." % (archive.filename,))
        self.stdout.write("Archive status is: %s." % (archive.status,))
        self.stdout.write("")

    def archive_transactions(self, account, months, delete):
        for month in months:
            self.archive_month_transactions(account, month, delete)

    def handle(self, *args, **opts):
        user = get_user_by_email(opts['email_address'])
        account_number = user.get_profile().user_account
        account = Account.objects.get(account_number=account_number)

        months = [datetime.strptime(m, '%Y-%m') for m in opts['months']]

        if opts['no_statement']:
            missing_months = []
        else:
            missing_months = self.missing_statement_months(account, months)

        if missing_months:
            self.stderr.write(
                "Aborting archiving, no statements found for the "
                "following months:")

            for m in missing_months:
                self.stderr.write(datetime.strftime(m, '%Y-%m'))
        else:
            self.stdout.write(
                "Archiving transactions for account %s..."
                % (opts['email_address'],))
            self.archive_transactions(account, months, opts['delete'])
