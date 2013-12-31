import csv
import xlrd
import StringIO

from django import forms
from django.utils.translation import ugettext_lazy as _

from go.services.forms import AjaxFormMixin, BaseServiceForm
from go.services.voucher_utils import BaseVoucherPoolForm
from go.services.airtime import settings as service_settings


class VoucherPoolForm(BaseVoucherPoolForm):
    """Form for an airtime voucher pool"""

    VOUCHERS_FILE_LABEL = _("Select a file from your hard drive containing "
                            "the airtime vouchers")

    VOUCHERS_FILE_HELP_TEXT = _("""
    <ul>
        <li>The file must either be a double quoted UTF encoded CSV or an
            Excel spreadsheet.</li>
        <li>Please ensure the file has the following headers:<br/>
        <b>operator</b>,<b>denomination</b>,<b>voucher</b></li>
        <li>Please ensure your file contains only one currency of
            vouchers.</li>
    </ul>
    """)

    POOL_NAME_LABEL = _("Provide a name for your airtime voucher pool")

    def __init__(self, *args, **kwargs):
        self.voucher_pool = kwargs.pop('voucher_pool', None)
        super(VoucherPoolForm, self).__init__(*args, **kwargs)

        if self.voucher_pool:
            self.fields.pop('pool_name')
        else:
            self.fields['pool_name'].label = self.POOL_NAME_LABEL

        self.fields['vouchers_file'].label = self.VOUCHERS_FILE_LABEL
        self.fields['vouchers_file'].help_text = self.VOUCHERS_FILE_HELP_TEXT

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
        if list(headings) != list(service_settings.FILE_FORMAT):
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
            if sheet.ncols != len(service_settings.FILE_FORMAT):
                raise forms.ValidationError("Invalid file format.")

            headings = [sheet.cell(0, 0).value, sheet.cell(0, 1).value,
                        sheet.cell(0, 2).value]

            if headings != list(service_settings.FILE_FORMAT):
                raise forms.ValidationError("Invalid file format.")
        finally:
            book.release_resources()

    def clean_pool_name(self):
        """Make sure the user doesn't already have a pool with the
        given name.
        """
        pool_name = self.cleaned_data.get('pool_name', None)
        voucher_pool_store = self.user_api.airtime_voucher_pool_store
        voucher_pool = voucher_pool_store.get_voucher_pool_by_name(pool_name)
        if voucher_pool:
            raise forms.ValidationError(
                "A pool with the given name already exists.")

        return pool_name

    def import_vouchers(self):
        """Upload the vouchers and create a new airtime voucher pool if one
        does not exist.
        """
        if not self.voucher_pool:
            pool_name = self.cleaned_data['pool_name']
            config = {'ext_pool_name': self._make_ext_pool_name(pool_name)}
            voucher_pool_store = self.user_api.airtime_voucher_pool_store
            self.voucher_pool = voucher_pool_store.new_voucher_pool(
                pool_name, config, imports=list())

        self._import_vouchers(self.voucher_pool)


class VoucherQueryForm(BaseServiceForm, AjaxFormMixin):
    """Form used for querying airtime vouchers"""

    messages = []

    msisdn = forms.CharField(
        max_length=20, label=_("Enter the MSISDN"))

    def __init__(self, *args, **kwargs):
        self.voucher_pool = kwargs.pop('voucher_pool')
        super(VoucherQueryForm, self).__init__(*args, **kwargs)
        self.messages = []

    def submit_query(self):
        """Query the voucher pool for the given MSISDN"""
        msisdn = self.cleaned_data['msisdn']
        results = self.service_def.voucher_service.audit_query(
            self.voucher_pool, msisdn)

        if results:
            pass  # TODO: Parse results and construct messages
        else:
            self.messages.append(
                _("There is no airtime voucher associated with MSISDN "
                  "'%(msisdn)s'.") % {'msisdn': msisdn})
