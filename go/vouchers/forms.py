import re
import csv
import xlrd
import StringIO

from django.conf import settings
from django import forms
from django.utils.translation import ugettext_lazy as _

from go.vouchers import settings as app_settings
from go.vouchers.models import VoucherPool
from go.vouchers.services import AirtimeVoucherService


class BaseVoucherPoolForm(forms.ModelForm):

    EXCEL_CONTENT_TYPES = (
        'application/vnd.ms-excel',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )

    CSV_CONTENT_TYPES = (
        'text/csv',
    )

    class Meta:
        model = VoucherPool
        fields = ['pool_name', 'pool_type']

    vouchers_file = forms.FileField()

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

    def clean_pool_name(self):
        """Make sure the user doesn't already have a pool with the
        given name.
        """
        pool_name = self.cleaned_data.get('pool_name', None)
        pool_exists = VoucherPool.objects.filter(
            pool_name__iexact=pool_name).exists()

        if pool_exists:
            raise forms.ValidationError(
                "A pool with the given name already exists.")

        return pool_name

    def _make_ext_pool_name(self, pool_name):
        """Return a unique name for the pool to be used in the external
        voucher service.
        """
        account = self.user.get_account()
        pool_name = re.sub(r'\W+', '_', pool_name.strip().lower())
        return "%s%s_%s" % (settings.GO_POOL_NAME_PREFIX,
                            account.account_number, pool_name)

    def _import_csv_file(self, voucher_pool):
        """Import the voucher CSV into the Airtime Voucher service.

        The value of ``go.vouchers.settings.REQUEST_RECORD_LIMIT`` dictates
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
                if record_count >= app_settings.REQUEST_RECORD_LIMIT:
                    self.voucher_service.import_vouchers(
                        voucher_pool, vouchers_file.name, content.getvalue())

                    content.close()
                    content = StringIO.StringIO()
                    writer = csv.writer(content)
                    writer.writerow(headings)
                    record_count = 0

            if record_count > 0:
                self.voucher_service.import_vouchers(
                    voucher_pool, vouchers_file.name, content.getvalue())

            content.close()

        finally:
            csvfile.close()

    def _import_excel_file(self, voucher_pool):
        """Import the voucher Excel sheet into the Airtime Voucher service.

        The value of ``go.vouchers.settings.REQUEST_RECORD_LIMIT`` dictates
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
                if record_count >= app_settings.REQUEST_RECORD_LIMIT:
                    self.voucher_service.import_vouchers(
                        voucher_pool, vouchers_file.name, content.getvalue())

                    content.close()
                    content = StringIO.StringIO()
                    writer = csv.writer(content)
                    writer.writerow(headings)
                    record_count = 0

            if record_count > 0:
                self.voucher_service.import_vouchers(
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


class AirtimeVoucherPoolForm(BaseVoucherPoolForm):
    """A form used to create a new *Airtime* `VoucherPool`"""

    VOUCHERS_FILE_LABEL = _("Select a file from your hard drive containing "
                            "the airtime vouchers")

    VOUCHERS_FILE_HELP_TEXT = """
    <ul>
        <li>The file must either be a double quoted UTF encoded CSV or an
            Excel spreadsheet.</li>
        <li>Please ensure the file has the following headers:<br/>
        <b>operator</b>,<b>denomination</b>,<b>voucher</b></li>
        <li>Please ensure your file contains only one currency of
            vouchers.</li>
    </ul>
    """

    POOL_NAME_LABEL = _("Provide a name for your airtime voucher pool")

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super(AirtimeVoucherPoolForm, self).__init__(*args, **kwargs)

        if 'pool_name' in self.fields:
            self.fields['pool_name'].label = self.POOL_NAME_LABEL

        self.fields['pool_type'].widget = forms.HiddenInput()
        self.fields['pool_type'].initial = VoucherPool.POOL_TYPE_AIRTIME

        self.fields['vouchers_file'].label = self.VOUCHERS_FILE_LABEL
        self.fields['vouchers_file'].help_text = self.VOUCHERS_FILE_HELP_TEXT

        self.voucher_service = AirtimeVoucherService()

    def _validate_csv_format(self):
        """Validate the CSV file format"""
        vouchers_file = self.cleaned_data['vouchers_file']
        if (hasattr(vouchers_file, 'temporary_file_path')):
            with open(vouchers_file.temporary_file_path, 'rb') as csvfile:
                reader = csv.reader(csvfile)
                headings = reader.next()
        else:  # File is stored in memory
            csvfile = StringIO.StringIO(vouchers_file.read())
            try:
                reader = csv.reader(csvfile)
                headings = reader.next()
            finally:
                csvfile.close()
        if list(headings) != list(app_settings.AIRTIME_VOUCHER_FILE_FORMAT):
            raise forms.ValidationError(
                "Invalid file format.")

    def _validate_excel_format(self):
        """Validate the Excel spreadsheet format"""
        vouchers_file = self.cleaned_data['vouchers_file']
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
            if sheet.ncols != len(app_settings.AIRTIME_VOUCHER_FILE_FORMAT):
                raise forms.ValidationError("Invalid file format.")

            headings = [sheet.cell(0, 0).value, sheet.cell(0, 1).value,
                        sheet.cell(0, 2).value]

            if headings != list(app_settings.AIRTIME_VOUCHER_FILE_FORMAT):
                raise forms.ValidationError("Invalid file format.")
        finally:
            book.release_resources()

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

        self._import_vouchers(instance)

        return instance


class AirtimeVoucherImportForm(AirtimeVoucherPoolForm):
    """A form used for importing airtime vouchers into an existing pool"""

    class Meta:
        model = VoucherPool
        exclude = ['user', 'pool_name', 'ext_pool_name', 'date_created']


class AirtimeVoucherQueryForm(forms.Form):
    """Form used for querying airtime vouchers"""

    msisdn = forms.CharField(
        max_length=20, label=_("Enter the MSISDN"))

    def __init__(self, *args, **kwargs):
        super(AirtimeVoucherQueryForm, self).__init__(*args, **kwargs)
        self.voucher_service = AirtimeVoucherService()
        self.messages = []

    def query(self, voucher_pool):
        """Query the voucher pool for the given MSISDN"""
        msisdn = self.cleaned_data['msisdn']
        results = self.voucher_service.audit_query(voucher_pool, msisdn)
        if results:
            pass  # TODO: Parse results and construct messages
        else:
            self.messages.append(_("There is no airtime voucher associated "
                                   "with this MSISDN."))
