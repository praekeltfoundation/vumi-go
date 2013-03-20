import xlrd

from django.utils.datastructures import SortedDict

from go.contacts.parsers.base import ContactFileParser, ContactParserException


class XLSFileParser(ContactFileParser):

    def read_data_from_file(self, file_path, field_names, has_header):
        book = xlrd.open_workbook(self.get_real_path(file_path))
        sheet = book.sheet_by_index(0)
        start_at = 1 if has_header else 0
        for row_number in range(start_at, sheet.nrows):
            row = sheet.row_values(row_number)
            # Only process rows that actually have data
            if any([column for column in row]):
                yield dict(zip(field_names,
                        sheet.row_values(row_number)[:len(field_names)]))

    def guess_headers_and_row(self, file_path):
        book = xlrd.open_workbook(self.get_real_path(file_path))
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

        if self.is_header_row(first_row):
            sample_row = SortedDict(zip(first_row, second_row))
            for column in first_row:
                default_headers.setdefault(column, column)
            return True, default_headers, sample_row
        return (False, default_headers,
            SortedDict([(column, column) for column in first_row]))
