from optparse import make_option

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User

from go.base.utils import vumi_api_for_user
from go.vumitools.account import RoutingTableHelper


class Command(BaseCommand):
    help = "Manage the routing table for a Vumi Go user"

    LOCAL_OPTIONS = [
        make_option('--email-address',
            dest='email-address',
            help='Email address for the Vumi Go user'),
        make_option('--show',
            dest='show',
            action='store_true',
            default=False,
            help='Display the current routing table'),
        make_option('--no-migration',
            dest='no-migration',
            action='store_true',
            default=False,
            help='Avoid triggering a migration (only applies to --show)'),
        make_option('--delete',
            dest='delete',
            action='store_true',
            default=False,
            help='Delete the routing table (setting it to None)'),
        make_option('--clear',
            dest='clear',
            action='store_true',
            default=False,
            help='Clear the routing table (setting it to {})'),
        make_option('--add',
            dest='add',
            nargs=4,
            default=(),
            help='Add a routing table entry with four params: '
                    'src_conn src_endpoint dest_conn dest_endpoint'),
        make_option('--remove',
            dest='remove',
            nargs=4,
            default=(),
            help='Remove the routing table entry with four params: '
                    'src_conn src_endpoint dest_conn dest_endpoint'),
    ]
    option_list = BaseCommand.option_list + tuple(LOCAL_OPTIONS)

    CONFLICTING_OPTIONS = ['show', 'delete', 'clear', 'add', 'remove']

    def handle(self, *args, **options):
        options = options.copy()
        for opt in self.LOCAL_OPTIONS:
            if options.get(opt.dest) is None:
                value = raw_input("%s: " % (opt.help,))
                if value:
                    options[opt.dest] = value
                else:
                    raise CommandError('Please provide %s:' % (opt.dest,))

        command_options = [c for c in self.CONFLICTING_OPTIONS if options[c]]
        if len(command_options) != 1:
            raise CommandError('Please provide exactly one of: %s' % (
                ['--%s' % c for c in self.CONFLICTING_OPTIONS],))

        try:
            user = User.objects.get(username=options['email-address'])
        except User.DoesNotExist, e:
            raise CommandError(e)
        user_api = vumi_api_for_user(user)

        if options['show']:
            return self.handle_show(user_api, options)
        elif options['delete']:
            return self.handle_delete(user_api, options)
        elif options['clear']:
            return self.handle_clear(user_api, options)
        elif options['add']:
            return self.handle_add(user_api, options)
        elif options['remove']:
            return self.handle_remove(user_api, options)
        raise NotImplementedError('Unknown command.')

    def handle_show(self, user_api, options):
        if options['no-migration']:
            self.print_routing_table(user_api.get_user_account().routing_table)
        else:
            self.print_routing_table(user_api.get_routing_table())

    def handle_delete(self, user_api, options):
        account = user_api.get_user_account()
        account.routing_table = None
        account.save()
        self.stdout.write("Routing table deleted.\n")

    def handle_clear(self, user_api, options):
        account = user_api.get_user_account()
        account.routing_table = {}
        account.save()
        self.stdout.write("Routing table cleared.\n")

    def handle_add(self, user_api, options):
        account = user_api.get_user_account()
        if account.routing_table is None:
            raise CommandError("No routing table found.")
        rt_helper = RoutingTableHelper(account.routing_table)
        rt_helper.add_entry(*options['add'])
        # TODO: Validation
        account.save()
        self.stdout.write("Routing table entry added.\n")

    def handle_remove(self, user_api, options):
        src_conn, src_endpoint, dst_conn, dst_endpoint = options['remove']
        account = user_api.get_user_account()
        if account.routing_table is None:
            raise CommandError("No routing table found.")
        rt_helper = RoutingTableHelper(account.routing_table)
        target = rt_helper.lookup_target(src_conn, src_endpoint)
        if target is None:
            raise CommandError("No routing entry found for (%s, %s)." % (
                src_conn, src_endpoint))
        elif target != [dst_conn, dst_endpoint]:
            raise CommandError(
                "Existing entry (%s, %s) does not match (%s, %s)." % (
                    target[0], target[1], dst_conn, dst_endpoint))
        rt_helper.remove_entry(src_conn, src_endpoint)
        # TODO: Validation
        account.save()
        self.stdout.write("Routing table entry removed.\n")

    def print_routing_table(self, routing_table):
        if routing_table is None:
            self.stdout.write("No routing table found.\n")
            return

        if not routing_table:
            self.stdout.write("The routing table is empty.\n")
            return

        self.stdout.write("Routing table:\n")
        for source, values in routing_table.iteritems():
            self.stdout.write("  %s\n" % (source,))
            for endpoint, dest in values.iteritems():
                self.stdout.write("      %s  ->  %s - %s\n" % (
                    endpoint, dest[0], dest[1]))
