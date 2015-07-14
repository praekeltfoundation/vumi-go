import os.path

from vumi.utils import load_class, normalize_msisdn


class ContactParserException(Exception):
    pass


class FieldNormalizerException(Exception):
    pass


class FieldNormalizer(object):
    """
    Normalizes values before import. This is primarily important for our
    XLSFileParser. MS Excel does some "intelligent" handling of values it
    tries to store. This particularly affects MSISDNs and numeric values.
    XLS stores MSISDNs such as '0761234567' (str) as `761234567.0` (float).
    The same applies for Integers '2' (str) becomes `2.0` (float) when
    read from the file itself.

    NOTE:   If `normalize()` is called with the name of an unknown normalizer
            then it is returned as is and no warning or exception is raised.
            This class only touches values if it knows what to do with it and
            does not do any type of validation.
    """

    def __init__(self, encoding='utf-8', encoding_errors='strict'):
        self.normalizers = [
            ('', 'Leave as is'),
            ('string', 'Plain Text'),
            ('integer', 'Whole Numbers (0, 10, 245, ... )'),
            ('float', 'Numbers (0.1, 3.14, 4.165, ...)'),
            ('msisdn_za', 'South African contact number (+27)'),
            ('msisdn_ke', 'Kenyan contact number (+254)'),
            ('msisdn_ug', 'Ugandan contact number (+256)'),
            ('msisdn_gh', 'Ghanaian contact number (+233)'),
            ('msisdn_cm', 'Cameroonian contact number (+237)'),
            ('msisdn_ng', 'Nigerian contact number (+234)'),
            ('msisdn_tz', 'Tanzanian contact number (+255)'),
            ('msisdn_int',
                'Contact number (already prefixed with country code)'),
        ]
        self.encoding = encoding
        self.encoding_errors = encoding_errors

    def __iter__(self):
        return iter(self.normalizers)

    def normalize(self, name, value):
        normalizer = getattr(self, 'normalize_%s' % (name,), lambda v: v)
        return normalizer(value)

    def normalize_string(self, value):
        if value is not None:
            try:
                return unicode(value, self.encoding, self.encoding_errors)
            except TypeError:
                return unicode(value)

    def is_numeric(self, value):
        str_value = self.normalize_string(value)
        try:
            float(str_value)
            return True
        except ValueError:
            return False

    def normalize_integer(self, value):
        if value and self.is_numeric(value):
            return int(float(value))
        return value

    def normalize_float(self, value):
        if value and self.is_numeric(value):
            return float(value)
        return value

    def lchop(self, string, chops):
        string = self.normalize_string(string)
        for chop in chops:
            if string.startswith(chop):
                string = string[len(chop):]
        return string

    def do_msisdn(self, value, country_code):
        value = self.normalize_string(value)
        value = self.lchop(value, ['+'])
        float_value = self.normalize_float(value)
        if not (self.is_numeric(value) and float_value.is_integer()):
            raise FieldNormalizerException('Invalid MSISDN: %s' % (value,))

        msisdn = self.normalize_string(self.normalize_integer(float_value))
        msisdn = self.lchop(msisdn, [country_code])
        msisdn = '0%s' % (msisdn,)
        return self.normalize_string(normalize_msisdn(msisdn, country_code))

    def normalize_msisdn_za(self, value):
        return self.do_msisdn(value, '27')

    def normalize_msisdn_ke(self, value):
        return self.do_msisdn(value, '254')

    def normalize_msisdn_ug(self, value):
        return self.do_msisdn(value, '256')

    def normalize_msisdn_gh(self, value):
        return self.do_msisdn(value, '233')

    def normalize_msisdn_cm(self, value):
        return self.do_msisdn(value, '237')

    def normalize_msisdn_ng(self, value):
        return self.do_msisdn(value, '234')

    def normalize_msisdn_tz(self, value):
        return self.do_msisdn(value, '255')

    def normalize_msisdn_int(self, value):
        value = self.normalize_string(value)
        value = self.lchop(value, ['+', '00'])
        float_value = self.normalize_float(value)
        if not (self.is_numeric(value) and float_value.is_integer()):
            raise FieldNormalizerException('Invalid MSISDN: %s' % (value,))

        msisdn = self.normalize_string(self.normalize_integer(float_value))
        country_code = msisdn[:3]
        return self.normalize_string(normalize_msisdn(msisdn, country_code))


class ContactFileParser(object):

    DEFAULT_HEADERS = {
        'key': 'UUID',
        'created_at': 'Creation Date',
        'name': 'Name',
        'surname': 'Surname',
        'bbm_pin': 'BBM Pin',
        'msisdn': 'Contact Number',
        'gtalk_id': 'GTalk (or XMPP) address',
        'dob': 'Date of Birth',
        'facebook_id': 'Facebook ID',
        'twitter_handle': 'Twitter handle',
        'email_address': 'Email address',
        'mxit_id': 'Mxit ID',
        'wechat_id': 'WeChat ID',
    }

    ENCODING = 'utf-8'
    ENCODING_ERRORS = 'strict'

    SETTABLE_ATTRIBUTES = set(DEFAULT_HEADERS.keys())

    def __init__(self):
        self.normalizer = FieldNormalizer()

    def get_real_path(self, file_path):
        from django.core.files.storage import default_storage
        return default_storage.path(file_path)

    def is_header_row(self, columns):
        """
        Determines whether the given columns have something that might hint
        at the row being a row with column headers and not column values.
        """
        column_set = set([column.lower().strip() for column in columns])
        hint_set = set(['phone', 'contact', 'msisdn', 'number', 'key'])
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

    def parse_file(self, file_path, fields, has_header):
        """
        Parses the file and returns dictionaries ready to be fed
        the ContactStore.new_contact method.

        We need to know what we cannot set to avoid a file import overwriting
        things like account details. Attributes that can be set are in the
        SETTABLE_ATTRIBUTES list, which defaults to the DEFAULT_HEADERS keys.
        """
        # We receive the fields as list of tuples, not a dict because the
        # order is important and needs to stay intact while being encoded
        # and decoded as JSON
        field_names = [field[0] for field in fields]
        field_map = dict(fields)
        # We're expecting a generator so loop over it and save as contacts
        # in the contact_store, normalizing anything we need to
        data_dictionaries = self.read_data_from_file(
            file_path, field_names, has_header)
        for data_dictionary in data_dictionaries:

            # Populate this with whatever we'll be sending to the
            # contact to be saved
            contact_dictionary = {}
            for key, value in data_dictionary.items():
                value = self.normalizer.normalize(field_map[key], value)
                if not isinstance(value, basestring):
                    value = unicode(str(value), self.ENCODING,
                                    self.ENCODING_ERRORS)
                elif isinstance(value, str):
                    value = unicode(value, self.ENCODING,
                                    self.ENCODING_ERRORS)

                if value is None or value == '':
                    continue

                if key in self.SETTABLE_ATTRIBUTES:
                    contact_dictionary[key] = value
                else:
                    extra = contact_dictionary.setdefault('extra', {})
                    extra[key] = value

            yield contact_dictionary
