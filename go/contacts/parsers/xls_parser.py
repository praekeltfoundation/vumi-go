import xlrd
import os.path

from django.utils.datastructures import SortedDict
from django.conf import settings

from go.contacts.parsers.base import ContactFileParser, ContactParserException


class XLSFileParser(ContactFileParser):

    def read_data_from_file(self, xls_file, field_names):
        book = xlrd.open_workbook(xls_file)
        sheet = book.sheet_by_index(0)
        for row_number in range(sheet.nrows):
            row = sheet.row_values(row_number)
            # Only process rows that actually have data
            if any([column for column in row]):
                # Our Riak client requires unicode for all keys & values stored.
                unicoded_row = dict([(key, unicode(value, 'utf-8'))
                                        for key, value in row.items()])
                yield unicoded_row

    def guess_headers_and_row(self, file_path):
        book = xlrd.open_workbook(os.path.join(settings.MEDIA_ROOT, file_path))
        sheet = book.sheet_by_index(0)
        if sheet.nrows == 0:
            raise ContactParserException('Worksheet is empty.')
        elif sheet.nrows == 1:
            first_row = sheet.row_values(0)
            return (False, self.DEFAULT_HEADERS,
                SortedDict([(column, None) for column in first_row]))

        first_row = [unicode(value).lower() for value in sheet.row_values(0)]
        second_row = [unicode(value).lower() for value in sheet.row_values(1)]

        default_headers = self.DEFAULT_HEADERS.copy()

        # Importing here to prevent circular import errors
        if self.is_header_row(first_row):
            sample_row = SortedDict(zip(first_row, second_row))
            for column in first_row:
                default_headers.setdefault(column, column)
            return True, default_headers, sample_row
        return (False, default_headers,
            SortedDict([(column, None) for column in first_row]))
