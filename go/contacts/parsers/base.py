import os.path

from go.vumitools.contact import Contact

from vumi.utils import load_class


class ContactParserException(Exception):
    pass

class ContactFileParser(object):

    DEFAULT_HEADERS = {
        'name': 'Name',
        'surname': 'Surname',
        'bbm_pin': 'BBM Pin',
        'msisdn': 'Contact Number',
        'gtalk_id': 'GTalk (or XMPP) address',
        'dob': 'Date of Birth',
        'facebook_id': 'Facebook ID',
        'twitter_handle': 'Twitter handle',
        'email_address': 'Email address',
    }

    EXCLUDED_ATTRIBUTES = ['user_account', 'created_at', 'extra', 'groups']

    def is_header_row(self, columns):
        """
        Determines whether the given columns have something that might hint
        at the row being a row with column headers and not column values.
        """
        column_set = set([column.lower() for column in columns])
        hint_set = set(['phone', 'contact', 'msisdn', 'number'])
        return hint_set.intersection(column_set)

    @classmethod
    def get_file_extension(cls, file_name):
        name, extension = os.path.splitext(file_name)
        return extension[1:]

    @classmethod
    def get_parser(cls, file_name):
        extension = cls.get_file_extension(file_name)

        parser = {
            'csv': 'go.contacts.parsers.csv_parser.CSVFileParser',
            'xls': 'go.contacts.parsers.xls_parser.XLSFileParser',
            'xlsx': 'go.contacts.parsers.xls_parser.XLSFileParser',
        }.get(extension)

        if parser:
            parser_class = load_class(*parser.rsplit('.', 1))
            return (extension, parser_class())
        else:
            raise ContactParserException('No parser available for type %s' % (
                extension,))

    def guess_headers_and_row(self, file_path):
        """
        Take a sample from the file path and determine if it has a header
        and provide a sample of the header if found along with existing
        values matched against the known headers.

        returns a Tuple:

            (header_found, known_headers, sample_data_row)
        """
        raise NotImplementedError('Subclasses should implement this.')

    def read_data_from_file(self, file_path, field_names, has_header):
        """
        Read the data from the file returning dictionaries of `field_names`
        versus the values found.
        """
        raise NotImplementedError('Subclasses should implement this.')

    def parse_file(self, file_path, field_names, has_header,
        excluded_attributes=None):
        """
        Parses the file and returns dictionaries ready to be fed
        the ContactStore.new_contact method.

        We need to know what we cannot set to avoid a file import overwriting
        things like account details. Excluded attributes is a list of contact
        attributes that are to be ignored. Defaults to EXCLUDED_ATTRIBUTES
        """
        excluded_attributes = excluded_attributes or self.EXCLUDED_ATTRIBUTES

        known_attributes = set([attribute
            for attribute in Contact.field_descriptors.keys()
            if attribute not in excluded_attributes])

        # We're expecting a generator so loop over it and save as contacts
        # in the contact_store, normalizing anything we need to
        data_dictionaries = self.read_data_from_file(file_path, field_names,
            has_header)
        for data_dictionary in data_dictionaries:

            # Populate this with whatever we'll be sending to the
            # contact to be saved
            contact_dictionary = {}
            for key, value in data_dictionary.items():
                if key in known_attributes:
                    contact_dictionary[key] = value
                else:
                    extra = contact_dictionary.setdefault('extra', {})
                    extra[key] = value

            yield contact_dictionary

