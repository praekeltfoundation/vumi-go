import getpass
from optparse import make_option

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.management.commands import createsuperuser
from django.contrib.auth.models import User
from django.core import exceptions


class Command(BaseCommand):
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

    option_list = BaseCommand.option_list + tuple([
        make_option('--%s' % key, dest=key, help=help)
            for key, help, _ in PARAMS
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
            createsuperuser.is_valid_email(options['email-address'])
            email_address = options['email-address']
            password = options['password']
            name = options['name']
            surname = options['surname']
            user = User.objects.create_user(username=email_address,
                                email=email_address, password=password)
            user.first_name = name
            user.last_name = surname
            user.save()
        except exceptions.ValidationError, e:
            raise CommandError(e)
