from iso8601 import parse_date
from optparse import make_option

from go.billing.models import Account
from go.billing.tasks import archive_transactions
from go.base.command_utils import BaseGoCommand, get_user_by_email


class Command(BaseGoCommand):
    help = (
        "Archive transactions for an account over a "
        "specified time range to S3.")

    option_list = BaseGoCommand.option_list + (
        make_option(
            '--email-address', dest='email_address',
            help="Email address of the account to archive transactions for."),
        make_option(
            '--from', dest='from_date',
            help=("Date to start archiving transactions from in iso8601"
                  " format. E.g. 2014-03-01.")),
        make_option(
            '--to', dest='to_date',
            help=("Date to stop archiving transactions at in iso8601"
                  " format. E.g. 2014-03-30.")),
        make_option(
            '--delete', dest='delete', action="store_true", default=False,
            help=("Delete the transactions after uploading the archive."
                  " Default: FALSE.")),
    )

    def handle(self, *args, **opts):
        user = get_user_by_email(opts['email_address'])
        account_number = user.get_profile().user_account
        account = Account.objects.get(account_number=account_number)

        from_date = parse_date(opts['from_date'], default_timezone=None)
        to_date = parse_date(opts['to_date'], default_timezone=None)
        delete = opts['delete']

        archive = archive_transactions(
            account.id, from_date, to_date, delete=delete)

        self.stdout.write(
            "Transactions archived for account %s from %s to %s"
            % (opts['email_address'], archive.from_date, archive.to_date))
        self.stdout.write(
            "Archived to S3 as %s." % (archive.filename,))
        self.stdout.write(
            "Archive status is: %s." % (archive.status,))
