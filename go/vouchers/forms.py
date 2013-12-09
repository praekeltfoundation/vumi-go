import re
import csv
import xlrd
import StringIO

from django import forms

from go.vouchers import settings
from go.vouchers.models import AirtimeVoucherPool
from go.vouchers.services import AirtimeVoucherService


class AirtimeVoucherPoolForm(forms.ModelForm):
    """``ModelForm`` for ``go.vouchers.models.AirtimeVoucherPool``"""

    EXCEL_CONTENT_TYPES = (
        'application/vnd.ms-excel',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )

    CSV_CONTENT_TYPES = (
        'text/csv'
    )

    REQUIRED_COLUMNS = ('operator', 'denomination', 'voucher')

    class Meta:
        model = AirtimeVoucherPool
        fields = ['pool_name']

    vouchers_file = forms.FileField(
        label="Select a file from your hard drive containing the airtime "
              "vouchers",
        required=True,
        help_text="<ul><li>The file must either be a double quoted UTF "
                  "encoded CSV or an Excel spreadsheet.</li><li>Please "
                  "ensure the file has no column headers.</li><li>Please "
                  "ensure your file contains only one currency of vouchers."
                  "</li></ul>")

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super(AirtimeVoucherPoolForm, self).__init__(*args, **kwargs)
        if 'pool_name' in self.fields:
            self.fields['pool_name'].label = \
                "Provide a name for your airtime voucher pool"

        self.airtime_voucher_service = AirtimeVoucherService()

    def _validate_csv_format(self, vouchers_file):
        """Validate the CSV file format"""
        if (hasattr(vouchers_file, 'temporary_file_path')):
            with open(vouchers_file.temporary_file_path, 'rb') as csvfile:
                reader = csv.reader(csvfile)
                row = reader.next()
        else:  # File is stored in memory
            csvfile = StringIO.StringIO(vouchers_file.read())
            try:
                reader = csv.reader(csvfile)
                row = reader.next()
            finally:
                csvfile.close()
        if (len(row) < len(self.REQUIRED_COLUMNS)
                or row[0] != self.REQUIRED_COLUMNS[0]
                or row[1] != self.REQUIRED_COLUMNS[1]
                or row[2] != self.REQUIRED_COLUMNS[2]):
            raise forms.ValidationError(
                "Invalid file format.")

    def _validate_excel_format(self, vouchers_file):
        """Validate the Excel spreadsheet format"""
        if (hasattr(vouchers_file, 'temporary_file_path')):
            book = xlrd.open_workbook(vouchers_file.temporary_file_path)
        else:  # File is stored in memory
            book = xlrd.open_workbook(file_contents=vouchers_file.read())
        try:
            sheets = book.sheets()
            if not sheets:
                raise forms.ValidationError(
                    "The file is empty.")

            sheet = sheets[0]
            if (sheet.cell(0, 0).value != self.REQUIRED_COLUMNS[0]
                    or sheet.cell(0, 1).value != self.REQUIRED_COLUMNS[1]
                    or sheet.cell(0, 2).value != self.REQUIRED_COLUMNS[2]):
                raise forms.ValidationError(
                    "Invalid file format.")
        finally:
            book.release_resources()

    def clean_vouchers_file(self):
        """Ensure that the uploaded file is either a CSV file or an Excel
        spreadsheet and validate the file format.
        """
        vouchers_file = self.cleaned_data['vouchers_file']
        if vouchers_file.content_type in self.CSV_CONTENT_TYPES:
            self._validate_csv_format(vouchers_file)

        elif vouchers_file.content_type in self.EXCEL_CONTENT_TYPES:
            self._validate_excel_format(vouchers_file)

        else:
            raise forms.ValidationError(
                "Please select either a CSV file or an Excel spreadsheet.")

        return vouchers_file

    def clean_pool_name(self):
        """Make sure the user doesn't already have a pool with the
        given name.
        """
        pool_name = self.cleaned_data.get('pool_name', '')
        if AirtimeVoucherPool.objects.filter(
                pool_name__iexact=pool_name).exists():
            raise forms.ValidationError(
                "A pool with the given name already exists.")
        return pool_name

    def _make_ext_pool_name(self, pool_name):
        """Return a unique name for the pool to be used in the Airtime
        Voucher service.
        """
        pool_name = pool_name.strip().lower()
        return "user_%d_%s" % (self.user.id,
                               re.sub(r'\W+', '_', pool_name))

    def _import_csv_file(self, pool_name, vouchers_file):
        """Import the voucher CSV into the Airtime Voucher service.

        The value of ``go.vouchers.settings.REQUEST_RECORD_LIMIT`` dictates
        when to split the import into multiple requests.
        """
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
                if record_count >= settings.REQUEST_RECORD_LIMIT:
                    self.airtime_voucher_service.import_vouchers(
                        pool_name, content.getvalue())
                    content.close()
                    content = StringIO.StringIO()
                    writer = csv.writer(content)
                    writer.writerow(headings)
                    record_count = 0

            if record_count > 0:
                self.airtime_voucher_service.import_vouchers(
                    pool_name, content.getvalue())
            content.close()

        finally:
            csvfile.close()

    def _import_excel_file(self, pool_name, vouchers_file):
        """Import the voucher Excel sheet into the Airtime Voucher service.

        The value of ``go.vouchers.settings.REQUEST_RECORD_LIMIT`` dictates
        when to split the import into multiple requests.
        """
        if (hasattr(vouchers_file, 'temporary_file_path')):
            filepath = vouchers_file.temporary_file_path()
            book = xlrd.open_workbook(filepath)
        else:  # File is stored in memory
            book = xlrd.open_workbook(file_contents=vouchers_file.read())
        try:
            sheet = book.sheets()[0]
            headings = [
                sheet.cell(0, 0).value,
                sheet.cell(0, 1).value,
                sheet.cell(0, 2).value]

            content = StringIO.StringIO()
            writer = csv.writer(content)
            writer.writerow(headings)
            record_count = 0
            for row in xrange(1, sheet.nrows):
                writer.writerow([
                    sheet.cell(row, 0).value,
                    sheet.cell(row, 1).value,
                    sheet.cell(row, 2).value])

                record_count += 1
                if record_count >= settings.REQUEST_RECORD_LIMIT:
                    self.airtime_voucher_service.import_vouchers(
                        pool_name, content.getvalue())
                    content.close()
                    content = StringIO.StringIO()
                    writer = csv.writer(content)
                    writer.writerow(headings)
                    record_count = 0

            if record_count > 0:
                self.airtime_voucher_service.import_vouchers(
                    pool_name, content.getvalue())
            content.close()

        finally:
            book.release_resources()

    def _import_vouchers(self, pool_name):
        """Import the vouchers from the uploaded file"""
        vouchers_file = self.cleaned_data['vouchers_file']
        vouchers_file.seek(0)
        if vouchers_file.content_type in self.CSV_CONTENT_TYPES:
            self._import_csv_file(pool_name, vouchers_file)

        elif vouchers_file.content_type in self.EXCEL_CONTENT_TYPES:
            self._import_excel_file(pool_name, vouchers_file)

    def save(self, *args, **kwargs):
        """Upload the vouchers and create a new Airtime Voucher pool if one
        does not exist.
        """
        kwargs['commit'] = False
        instance = super(AirtimeVoucherPoolForm, self).save(
            *args, **kwargs)

        if not instance.id:
            instance.user = self.user
            pool_name = self.cleaned_data.get('pool_name')
            instance.ext_pool_name = self._make_ext_pool_name(pool_name)

        instance.save()

        self._import_vouchers(instance.ext_pool_name)

        return instance


class AirtimeVoucherImportForm(AirtimeVoucherPoolForm):
    """A form used for importing airtime vouchers into an existing pool"""

    class Meta:
        model = AirtimeVoucherPool
        exclude = ['user', 'pool_name', 'ext_pool_name', 'date_created']
