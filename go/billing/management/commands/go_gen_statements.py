from datetime import datetime
from optparse import make_option

from go.billing.models import Account
from go.billing.tasks import month_range, generate_monthly_statement
from go.base.command_utils import BaseGoCommand, get_user_by_email


class Command(BaseGoCommand):
    help = "Generate monthly billing statements for an account."

    option_list = BaseGoCommand.option_list + (
        make_option(
            '--email-address', dest='email_address',
            help="Email address of the account to generate statements for."),
        make_option(
            '--month', dest='month', action='append',
            help="Month to generate statements for in the form YYYY-MM, "
            "e.g. 2014-01. Multiple may be specified."))

    def handle(self, *args, **opts):
        user = get_user_by_email(opts['email_address'])
        account_number = user.get_profile().user_account
        account = Account.objects.get(account_number=account_number)

        self.stdout.write(
            "Generating statements for account %s..."
            % (opts['email_address'],))

        months = [datetime.strptime(m, '%Y-%m') for m in opts['month']]

        for month in months:
            from_date, to_date = month_range(0, month)
            generate_monthly_statement(account.id, from_date, to_date)

            self.stdout.write(
                "Generated statement for %s."
                % (datetime.strftime(month, '%Y-%m'),))
