from optparse import make_option

from django.core.management.base import BaseCommand, CommandError

from go.base.utils import vumi_api_for_user
from go.base.command_utils import get_user_by_email


class Command(BaseCommand):
    help = "Give a Vumi Go user access to a certain tagpool"

    LOCAL_OPTIONS = (
        make_option('--email-address',
            dest='email-address',
            help='Email address for the Vumi Go user'),
        make_option('--add-credit',
            dest='add-credit',
            help='Amount of credit to add'),
    )
    option_list = BaseCommand.option_list + LOCAL_OPTIONS

    def handle(self, *args, **options):
        options = options.copy()
        if options['add-credit'] is not None:
            try:
                options['add-credit'] = int(options['add-credit'])
            except:
                raise CommandError("--add-credit only accepts integers")
        self.handle_validated(*args, **options)

    def handle_validated(self, *args, **options):
        email_address = options['email-address']
        add_credit = options['add-credit']

        user = get_user_by_email(email_address)
        user_api = vumi_api_for_user(user)

        if add_credit is not None:
            self.add_credit(user_api, add_credit)

        self.show_credit(user_api, email_address)

    def add_credit(self, user_api, amount):
        user_api.api.cm.credit(user_api.user_account_key, amount)
        print "%d credit(s) added." % amount

    def show_credit(self, user_api, email_address):
        credit = user_api.api.cm.get_credit(user_api.user_account_key)
        if credit is None:
            print ("%s not present in credit manager"
                   " (use --add-credit to add them)" % email_address)
        else:
            print "%s now has %d credit(s)" % (email_address, credit)
