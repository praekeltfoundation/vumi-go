import csv
import xlrd
import StringIO


class UnsupportedContentType(Exception):
    """Raised when an invalid content type is encountered"""


class VoucherFileParser(object):
    """Base class for a voucher file parser"""

    def __init__(self, file_path, batch_limit=None):
        self.file_path = file_path
        self.batch_limit = batch_limit

    def read():
        raise NotImplementedError()


class ExcelParser(VoucherFileParser):
    """Parse Excel spreadsheets"""

    CONTENT_TYPES = (
        'application/vnd.ms-excel',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )

    def read(self):
        """Return at most ``self.batch_limit`` vouchers from the file"""
        book = xlrd.open_workbook(self.file_path)
        try:
            sheet = book.sheets()[0]

            headings = []
            for col in xrange(0, sheet.ncols):
                headings.append(sheet.cell(0, col).value)

            content = StringIO.StringIO()
            writer = csv.writer(content)
            writer.writerow(headings)
            record_count = 0
            for row in xrange(1, sheet.nrows):
                record = []
                for col in xrange(0, sheet.ncols):
                    record.append(sheet.cell(row, col).value)
                writer.writerow(record)
                record_count += 1

                if self.batch_limit and record_count >= self.batch_limit:
                    yield content.getvalue()

                    content.close()
                    content = StringIO.StringIO()
                    writer = csv.writer(content)
                    writer.writerow(headings)
                    record_count = 0

            if record_count > 0:
                yield content.getvalue()

            content.close()

        finally:
            book.release_resources()


class CsvParser(VoucherFileParser):
    """Parse CSV files"""

    CONTENT_TYPES = (
        'text/csv',
    )

    def read(self):
        """Return at most ``self.batch_limit`` vouchers from the file"""
        csvfile = open(self.file_path, 'rb')
        try:
            reader = csv.reader(csvfile)
            headings = reader.next()
            content = StringIO.StringIO()
            writer = csv.writer(content)
            writer.writerow(headings)
            record_count = 0
            for row in reader:
                writer.writerow(row)
                record_count += 1

                if self.batch_limit and record_count >= self.batch_limit:
                    yield content.getvalue()

                    content.close()
                    content = StringIO.StringIO()
                    writer = csv.writer(content)
                    writer.writerow(headings)
                    record_count = 0

            if record_count > 0:
                yield content.getvalue()

            content.close()

        finally:
            csvfile.close()


def get_parser(file_path, content_type, **kwargs):
    """Return the parser for the given ``content_type``"""
    if content_type in ExcelParser.CONTENT_TYPES:
        return ExcelParser(file_path, **kwargs)
    elif content_type in CsvParser.CONTENT_TYPES:
        return CsvParser(file_path, **kwargs)
    else:
        raise UnsupportedContentType(
            "There is no parser which supports %r files" % (content_type,))
