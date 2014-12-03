from iso8601 import parse_date
from optparse import make_option

from go.billing.models import Account
from go.billing.tasks import generate_monthly_statement
from go.base.command_utils import BaseGoCommand, get_user_by_email


class Command(BaseGoCommand):
    help = (
        "Generate a billing statement for an account over a "
        "specified time range.")

    option_list = BaseGoCommand.option_list + (
        make_option(
            '--email-address', dest='email_address',
            help="Email address of the account to generate statements for."),
        make_option(
            '--from', dest='from_date',
            help="Starting date of the statement in iso8601 format"),
        make_option(
            '--to', dest='to_date',
            help="Ending date of the statement in iso8601 format"))

    def handle(self, *args, **opts):
        user = get_user_by_email(opts['email_address'])
        account_number = user.get_profile().user_account
        account = Account.objects.get(account_number=account_number)

        from_date = parse_date(opts['from_date'])
        to_date = parse_date(opts['to_date'])

        generate_monthly_statement(account.id, from_date, to_date)

        self.stdout.write(
            "Statement generated for account %s from %s to %s"
            % (opts['email_address'], from_date, to_date))
