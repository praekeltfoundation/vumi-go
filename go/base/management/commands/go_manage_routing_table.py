from optparse import make_option

from go.base.command_utils import BaseGoAccountCommand, CommandError
from go.vumitools.routing_table import GoConnector, RoutingTable


class Command(BaseGoAccountCommand):
    help = "Manage the routing table for a Vumi Go user"

    COMMAND_OPTIONS = [
        make_option('--show',
            dest='show',
            action='store_true',
            default=False,
            help='Display the current routing table'),
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
    LOCAL_OPTIONS = []
    option_list = (
        BaseGoAccountCommand.option_list +
        tuple(COMMAND_OPTIONS) +
        tuple(LOCAL_OPTIONS))

    def handle_no_command(self, *args, **options):
        options = options.copy()
        for opt in self.LOCAL_OPTIONS:
            if options.get(opt.dest) is None:
                value = raw_input("%s: " % (opt.help,))
                if value:
                    options[opt.dest] = value
                else:
                    raise CommandError('Please provide %s:' % (opt.dest,))

        # Ensure a single option is chosen from the command options
        cmd_options = [c.dest for c in self.COMMAND_OPTIONS if options[c.dest]]
        if len(cmd_options) != 1:
            raise CommandError('Please provide exactly one of: %s' % (
                ['--%s' % c.dest for c in self.COMMAND_OPTIONS],))

        if options['show']:
            return self.handle_show(options)
        elif options['clear']:
            return self.handle_clear(options)
        elif options['add']:
            return self.handle_add(options)
        elif options['remove']:
            return self.handle_remove(options)
        raise NotImplementedError('Unknown command.')

    def handle_show(self, options):
        self.print_routing_table(self.user_api.get_routing_table())

    def handle_clear(self, options):
        account = self.user_api.get_user_account()
        account.routing_table = RoutingTable()
        account.save()
        self.stdout.write("Routing table cleared.\n")

    def handle_add(self, options):
        account = self.user_api.get_user_account()
        if account.routing_table is None:
            raise CommandError("No routing table found.")
        account.routing_table.add_entry(*options['add'])
        try:
            self.user_api.validate_routing_table(account)
        except Exception as e:
            raise CommandError(e)
        account.save()
        self.stdout.write("Routing table entry added.\n")

    def handle_remove(self, options):
        src_conn, src_endpoint, dst_conn, dst_endpoint = options['remove']
        account = self.user_api.get_user_account()
        if account.routing_table is None:
            raise CommandError("No routing table found.")
        target = account.routing_table.lookup_target(src_conn, src_endpoint)
        if target is None:
            raise CommandError("No routing entry found for (%s, %s)." % (
                src_conn, src_endpoint))
        elif target != [GoConnector.parse(dst_conn), dst_endpoint]:
            raise CommandError(
                "Existing entry (%s, %s) does not match (%s, %s)." % (
                    target[0], target[1], dst_conn, dst_endpoint))
        account.routing_table.remove_entry(src_conn, src_endpoint)
        try:
            self.user_api.validate_routing_table(account)
        except Exception as e:
            raise CommandError(e)
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
        for source, values in routing_table._routing_table.iteritems():
            self.stdout.write("  %s\n" % (source,))
            for endpoint, dest in values.iteritems():
                self.stdout.write("      %s  ->  %s - %s\n" % (
                    endpoint, dest[0], dest[1]))
