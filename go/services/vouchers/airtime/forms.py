import csv
import xlrd

from django import forms
from django.utils.translation import ugettext_lazy as _

from go.services.forms import AjaxFormMixin, BaseServiceForm
from go.services.vouchers.forms import BaseVoucherPoolForm
from go.services.vouchers.airtime import settings as service_settings
from go.services.vouchers.airtime.tasks import import_vouchers_file


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
        with open(vouchers_file.temporary_file_path(), 'rb') as csvfile:
            reader = csv.reader(csvfile)
            headings = reader.next()
        if list(headings) != list(service_settings.FILE_FORMAT):
            raise forms.ValidationError(
                "Invalid file format. Headers should be %r" %
                (service_settings.FILE_FORMAT,))

    def _validate_excel_format(self):
        """Validate the Excel spreadsheet format"""
        vouchers_file = self.cleaned_data['vouchers_file']
        book = xlrd.open_workbook(vouchers_file.temporary_file_path())
        try:
            sheets = book.sheets()
            if not sheets:
                raise forms.ValidationError(
                    "The file is empty.")

            sheet = sheets[0]
            headings = [sheet.cell(0, i).value for i in range(sheet.ncols)]
            if headings != list(service_settings.FILE_FORMAT):
                raise forms.ValidationError(
                    "Invalid file format. Headers should be %r" %
                    (service_settings.FILE_FORMAT,))

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

        vouchers_file = self.cleaned_data['vouchers_file']
        import_vouchers_file.delay(self.user_api.user_account_key,
                                   self.voucher_pool.key,
                                   vouchers_file.name,
                                   vouchers_file.temporary_file_path(),
                                   vouchers_file.content_type)


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
        results = self.service_def.voucher_service.query_msisdn(
            self.voucher_pool, msisdn)

        if results:
            response_data = results[0].get('response_data')
            self.messages.append(
                _("The airtime voucher associated with MSISDN "
                  "'%(msisdn)s' is '%(voucher)s'.")
                % {'msisdn': msisdn,
                   'voucher': response_data.get('voucher')})
        else:
            self.messages.append(
                _("There is no airtime voucher associated with MSISDN "
                  "'%(msisdn)s'.") % {'msisdn': msisdn})
