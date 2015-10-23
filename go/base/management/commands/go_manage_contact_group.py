from optparse import make_option

from go.base.command_utils import (
    BaseGoAccountCommand, CommandError, make_command_option)


class Command(BaseGoAccountCommand):
    help = "Manage contact groups belonging to a Vumi Go account."

    LOCAL_OPTIONS = [
        make_option('--group',
            dest='group',
            help='The contact group to operate on'),
        make_option('--query',
            dest='query',
            help='The query for a newly-created smart group'),
        make_command_option('list',
            help='List groups'),
        make_command_option('create',
            help='Create a new group'),
        make_command_option('create_smart',
            help='Create a new smart group'),
        make_command_option('delete',
            help='Delete a group'),
    ]
    option_list = BaseGoAccountCommand.option_list + tuple(LOCAL_OPTIONS)

    def ask_for_option(self, options, opt):
        if options.get(opt.dest) is None:
            value = raw_input("%s: " % (opt.help,))
            if value:
                options[opt.dest] = value
            else:
                raise CommandError('Please provide %s:' % (opt.dest,))

    def ask_for_options(self, options, opt_dests):
        for opt in self.LOCAL_OPTIONS:
            if opt.dest in opt_dests:
                self.ask_for_option(options, opt)

    def format_group(self, group):
        return '%s [%s] %s"%s"' % (
            group.key, group.created_at.strftime("%Y-%m-%d %H:%M"),
            '(smart) ' if group.is_smart_group() else '', group.name)

    def handle_command_list(self, *args, **options):
        groups = self.user_api.list_groups()
        if groups:
            for group in sorted(groups, key=lambda g: g.created_at):
                self.stdout.write(" * %s\n" % (self.format_group(group),))
        else:
            self.stdout.write("No contact groups found.\n")

    def handle_command_create(self, *args, **options):
        self.ask_for_options(options, ['group'])

        group = self.user_api.contact_store.new_group(
            options['group'].decode('utf-8'))
        self.stdout.write(
            "Group created:\n * %s\n" % (self.format_group(group),))

    def handle_command_create_smart(self, *args, **options):
        self.ask_for_options(options, ['group', 'query'])

        group = self.user_api.contact_store.new_smart_group(
            options['group'].decode('utf-8'), options['query'].decode('utf-8'))
        self.stdout.write(
            "Group created:\n * %s\n" % (self.format_group(group),))

    def handle_command_delete(self, *args, **options):
        # NOTE: There is a small chance that this can break when running in
        #       production if the load is high and the queues have backed up.
        #       What could happen is that while contacts are being removed from
        #       the group, new contacts could have been added before the group
        #       has been deleted. If this happens those contacts will have
        #       secondary indexes in Riak pointing to a non-existent Group.
        self.ask_for_options(options, ['group'])

        group = self.user_api.contact_store.get_group(options['group'])
        if group is None:
            raise CommandError(
                "Group '%s' not found. Please use the group key (UUID)." % (
                    options['group'],))
        self.stdout.write(
            "Deleting group:\n * %s\n" % (self.format_group(group),))
        # We do this one at a time because we're already saving them one at a
        # time and the boilerplate for fetching batches without having them all
        # sit in memory is ugly.
        contacts_page = group.backlinks.contact_keys()
        while contacts_page is not None:
            for contact_key in contacts_page:
                contact = self.user_api.contact_store.get_contact_by_key(
                    contact_key)
                contact.groups.remove(group)
                contact.save()
                self.stdout.write('.')
            contacts_page = contacts_page.next_page()
        self.stdout.write('\nDone.\n')
        group.delete()
