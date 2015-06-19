from optparse import make_option

from go.contacts.parsers import ContactFileParser

from go.base.command_utils import BaseGoCommand, CommandError


class Command(BaseGoCommand):
    help = "Manage contact groups belonging to a Vumi Go account."

    LOCAL_OPTIONS = [
        make_option('--email-address',
            dest='email-address',
            help='Email address for the Vumi Go user'),
        make_option('--contacts-csv',
            dest='contacts-csv',
            help='The CSV file containing contacts to import'),
        make_option('--group',
            dest='groups',
            action='append',
            default=[],
            help='Group to add the imported contacts to (multiple)'),
    ]
    option_list = BaseGoCommand.option_list + tuple(LOCAL_OPTIONS)

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

    def handle(self, *args, **options):
        options = options.copy()

        self.ask_for_options(options, ['email-address', 'contacts-csv'])
        user, user_api = self.mk_user_api(options['email-address'])
        groups = [g.key for g in user_api.list_groups()]
        for group in options['groups']:
            if group not in groups:
                raise CommandError('Group not found: %s' % (group,))
        return self.import_contacts(user_api, options)

    def import_contacts(self, user_api, options):
        file_path = options['contacts-csv']
        try:
            _, parser = ContactFileParser.get_parser(file_path)
            # No Django silliness, please.
            parser.get_real_path = lambda path: path
            has_header, _, row = parser.guess_headers_and_row(file_path)
            fields = [(h, '') for h in row]
            contact_dicts = parser.parse_file(file_path, fields, has_header)

            written_contacts = []
            self.stdout.write("Importing contacts:\n")
            try:
                for contact_dict in contact_dicts:
                    contact_dict['groups'] = options['groups']
                    c = user_api.contact_store.new_contact(**contact_dict)
                    written_contacts.append(c)
                    self.stdout.write('.')
            except:
                for contact in written_contacts:
                    contact.delete()
                raise
            self.stdout.write('\nDone.\n')

        except Exception, e:
            raise CommandError(e)
