import getpass
from optparse import make_option

from django.core.validators import validate_email
from django.core import exceptions
from django.contrib.auth import get_user_model

from go.base.command_utils import BaseGoCommand, CommandError

class Command(BaseGoCommand):
    help = "Create a Vumi Go user"

    PARAMS = [
        ('email-address', 'Email address for account to be created',
                raw_input),
        ('password', 'Password for account to be created',
                getpass.getpass),
        ('name', 'Name of the account holder',
                raw_input),
        ('surname', 'Surname of the account holder',
                raw_input),
    ]

    option_list = BaseGoCommand.option_list + tuple([
        make_option('--%s' % key, dest=key, help=hlp)
        for key, hlp, _ in PARAMS
    ])

    def handle(self, *args, **options):
        for key, help, input_func in self.PARAMS:
            if not options.get(key):
                value = input_func("%s: " % (help,))
                if value:
                    options[key] = value
                else:
                    self.stderr.write('Please provide %s:' % (key,))

        try:
            validate_email(options['email-address'])
            email_address = options['email-address']
            password = options['password']
            name = options['name']
            surname = options['surname']
            user_model = get_user_model()
            user = user_model.objects.create_user(
                email=email_address, password=password)
            user.first_name = name
            user.last_name = surname
            user.save()
        except exceptions.ValidationError, e:
            raise CommandError(e)
