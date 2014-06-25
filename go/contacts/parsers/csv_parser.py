import csv

from go.contacts.parsers import ContactFileParser, ContactParserException

from django.utils.datastructures import SortedDict


class CSVFileParser(ContactFileParser):
    DELIMITERS = ",|\t"

    @classmethod
    def _sniff(cls, csvfile):
        sample = csvfile.read(1024)
        csvfile.seek(0)

        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=cls.DELIMITERS)
        except csv.Error as e:
            for delimiter in cls.DELIMITERS:
                if delimiter in sample:
                    # We have a recognised delimiter, so our error must be
                    # something else.
                    raise ContactParserException(e)
            # If we get here, it's because we didn't find a recognised
            # delimiter. This probably means we have a single-column file and
            # the excel dialect should be fine for that.
            dialect = csv.excel

        return dialect

    def read_data_from_file(self, file_path, field_names, has_header):
        csvfile = open(self.get_real_path(file_path), 'rU')
        dialect = self._sniff(csvfile)

        try:
            reader = csv.DictReader(csvfile, field_names, dialect=dialect)
            if has_header:
                reader.next()
            for row in reader:
                if None in row:
                    # Any extra fields are stuck in a list with a key of
                    # `None`. The presence of this key means we have a row
                    # with too many fields. We don't know how to handle
                    # this case, so we abort.
                    raise ContactParserException(
                        'Invalid row: too many fields.')
                if None in row.values():
                    # Any missing fields are given a value of `None`. Since
                    # all legitimate field values are strings, this is a
                    # reliable indicator of a missing field. We don't know
                    # how to handle this case, so we abort.
                    raise ContactParserException(
                        'Invalid row: not enough fields.')

                # Only process rows that actually have data
                if any([column for column in row]):
                    # Our Riak client requires unicode for all keys & values
                    # stored.
                    unicoded_row = dict([(key, unicode(value or '', 'utf-8'))
                                         for key, value in row.items()])
                    yield unicoded_row
        except csv.Error as e:
            raise ContactParserException(e)

    def guess_headers_and_row(self, file_path):
        """
        Take a sample from the CSV data and determine if it has a header
        and provide a sample of the header if found along with existing
        values matched against the known headers.

        returns a Tuple:

            (header_found, known_headers, sample_data_row)
        """
        fp = open(self.get_real_path(file_path), 'rU')
        dialect = self._sniff(fp)

        first_row, second_row = None, None

        try:
            reader = csv.reader(fp, dialect=dialect)
            first_row = reader.next()
            second_row = reader.next()
        except StopIteration:
            if first_row is None:
                raise ContactParserException('Invalid CSV file.')

        default_headers = self.DEFAULT_HEADERS.copy()

        if self.is_header_row(first_row) and second_row is not None:
            sample_row = SortedDict(zip(first_row, second_row))
            for column in first_row:
                default_headers.setdefault(column, column)
            return True, default_headers, sample_row
        return (False, default_headers,
            SortedDict([(column, column) for column in first_row]))
