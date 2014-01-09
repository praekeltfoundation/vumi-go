import re
import csv
import xlrd
import StringIO

from django import forms

from go.services import settings as app_settings
from go.services.forms import AjaxFormMixin, BaseServiceForm


class BaseVoucherPoolForm(BaseServiceForm, AjaxFormMixin):
    """Base class for a voucher pool form"""

    EXCEL_CONTENT_TYPES = (
        'application/vnd.ms-excel',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )

    CSV_CONTENT_TYPES = (
        'text/csv',
    )

    REQUEST_RECORD_LIMIT = 10000

    pool_name = forms.CharField(max_length=255)
    vouchers_file = forms.FileField()

    def __init__(self, *args, **kwargs):
        self.user_api = kwargs.pop('user_api')
        super(BaseVoucherPoolForm, self).__init__(*args, **kwargs)

    def _validate_csv_format(self):
        """Validate the CSV file format"""
        raise NotImplementedError()

    def _validate_excel_format(self):
        """Validate the Excel spreadsheet format"""
        raise NotImplementedError()

    def clean_vouchers_file(self):
        """Ensure that the uploaded file is either a CSV file or an Excel
        spreadsheet and validate the file format.
        """
        vouchers_file = self.cleaned_data['vouchers_file']
        if vouchers_file.content_type in self.CSV_CONTENT_TYPES:
            self._validate_csv_format()

        elif vouchers_file.content_type in self.EXCEL_CONTENT_TYPES:
            self._validate_excel_format()

        else:
            raise forms.ValidationError(
                "Please select either a CSV file or an Excel spreadsheet.")

        return vouchers_file

    def _make_ext_pool_name(self, pool_name):
        """Return a unique name for the pool to be used in the external
        voucher service.
        """
        pool_name = re.sub(r'\W+', '_', pool_name.strip().lower())
        return "%s%s_%s" % (app_settings.VOUCHER_POOL_PREFIX,
                            self.user_api.user_account_key, pool_name)

    def _import_csv_file(self, voucher_pool):
        """Import the voucher CSV into the Airtime Voucher service.

        The value of ``self.REQUEST_RECORD_LIMIT`` dictates
        when to split the import into multiple requests.
        """
        vouchers_file = self.cleaned_data['vouchers_file']
        if (hasattr(vouchers_file, 'temporary_file_path')):
            filepath = vouchers_file.temporary_file_path()
            csvfile = open(filepath, 'rb')
        else:  # File is stored in memory
            csvfile = StringIO.StringIO(vouchers_file.read())
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
                if record_count >= self.REQUEST_RECORD_LIMIT:
                    self.service_def.voucher_service.import_vouchers(
                        voucher_pool, vouchers_file.name, content.getvalue())

                    content.close()
                    content = StringIO.StringIO()
                    writer = csv.writer(content)
                    writer.writerow(headings)
                    record_count = 0

            if record_count > 0:
                self.service_def.voucher_service.import_vouchers(
                    voucher_pool, vouchers_file.name, content.getvalue())

            content.close()

        finally:
            csvfile.close()

    def _import_excel_file(self, voucher_pool):
        """Import the voucher Excel sheet into the Airtime Voucher service.

        The value of ``self.REQUEST_RECORD_LIMIT`` dictates
        when to split the import into multiple requests.
        """
        vouchers_file = self.cleaned_data['vouchers_file']
        if (hasattr(vouchers_file, 'temporary_file_path')):
            filepath = vouchers_file.temporary_file_path()
            book = xlrd.open_workbook(filepath)
        else:  # File is stored in memory
            book = xlrd.open_workbook(file_contents=vouchers_file.read())
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
                if record_count >= self.REQUEST_RECORD_LIMIT:
                    self.service_def.voucher_service.import_vouchers(
                        voucher_pool, vouchers_file.name, content.getvalue())

                    content.close()
                    content = StringIO.StringIO()
                    writer = csv.writer(content)
                    writer.writerow(headings)
                    record_count = 0

            if record_count > 0:
                self.service_def.voucher_service.import_vouchers(
                    voucher_pool, vouchers_file.name, content.getvalue())

            content.close()

        finally:
            book.release_resources()

    def _import_vouchers(self, voucher_pool):
        """Import the vouchers from the uploaded file"""
        vouchers_file = self.cleaned_data['vouchers_file']
        vouchers_file.seek(0)
        if vouchers_file.content_type in self.CSV_CONTENT_TYPES:
            self._import_csv_file(voucher_pool)

        elif vouchers_file.content_type in self.EXCEL_CONTENT_TYPES:
            self._import_excel_file(voucher_pool)

    def import_vouchers(self):
        """Import the vouchers into the voucher pool.

        If the voucher pool does not yet exist create a new one.
        """
        raise NotImplementedError()
