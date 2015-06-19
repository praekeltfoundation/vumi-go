import uuid
from optparse import make_option

from go.base.utils import vumi_api_for_user
from go.base.command_utils import BaseGoCommand, CommandError, get_user_by_email


class Command(BaseGoCommand):
    help = "Give a Vumi Go user access to a certain application"

    LOCAL_OPTIONS = [
        make_option('--email-address',
            dest='email-address',
            help='Email address for the Vumi Go user'),
        make_option('--application-module',
            dest='application-module',
            help='The application module to give access to'),
        make_option('--enable',
            dest='enable',
            action='store_true',
            default=False,
            help='Give access to this application'),
        make_option('--disable',
            dest='disable',
            action='store_true',
            default=False,
            help='Revoke access to this application'),
    ]
    option_list = BaseGoCommand.option_list + tuple(LOCAL_OPTIONS)

    def handle(self, *args, **options):
        options = options.copy()
        for opt in self.LOCAL_OPTIONS:
            if options.get(opt.dest) is None:
                value = raw_input("%s: " % (opt.help,))
                if value:
                    options[opt.dest] = value
                else:
                    raise CommandError('Please provide %s:' % (opt.dest,))

        self.handle_validated(*args, **options)

    def handle_validated(self, *args, **options):
        email_address = options['email-address']
        application_module = unicode(options['application-module'])
        enable = options['enable']
        disable = options['disable']

        if (enable and disable) or not (enable or disable):
            raise CommandError(
                'Please specify either --enable or --disable.')

        user = get_user_by_email(email_address)
        account = user.get_profile().get_user_account()
        all_permissions = []
        for permissions in account.applications.load_all_bunches():
            all_permissions.extend(permissions)
        existing_applications = [p.application for p in all_permissions]

        if disable:
            if application_module in existing_applications:
                [permission] = [p for p in all_permissions
                                if p.application == application_module]
                self.disable_application(permission, account)
            else:
                raise CommandError('User does not have this permission')

        if enable:
            if application_module not in existing_applications:
                self.enable_application(user, account, application_module)
            else:
                raise CommandError('User already has this permission')

    def disable_application(self, app_permission, account):
        account.applications.remove(app_permission)
        account.save()

    def enable_application(self, user, account, application_module):
        user_api = vumi_api_for_user(user)
        api = user_api.api

        app_permission = api.account_store.application_permissions(
            uuid.uuid4().hex, application=application_module)
        app_permission.save()

        account.applications.add(app_permission)
        account.save()
