import csv
import xlrd

from django import forms
from django.utils.translation import ugettext_lazy as _

from go.services.forms import AjaxFormMixin, BaseServiceForm
from go.services.vouchers.forms import BaseVoucherPoolForm
from go.services.vouchers.unique_codes import settings as service_settings
from go.services.vouchers.unique_codes.tasks import import_unique_codes_file


class UniqueCodePoolForm(BaseVoucherPoolForm):
    """Form for a unique code pool"""

    VOUCHERS_FILE_LABEL = _("Select a file from your hard drive containing "
                            "the unique codes.")

    VOUCHERS_FILE_HELP_TEXT = _("""
    <ul>
        <li>The file must either be a double quoted UTF encoded CSV or an
            Excel spreadsheet.</li>
        <li>Please ensure the file has the following headers:<br/>
        <b>unique_code</b>,<b>flavour</b></li>
    </ul>
    """)

    POOL_NAME_LABEL = _("Provide a name for your unique code pool")

    def __init__(self, *args, **kwargs):
        self.unique_code_pool = kwargs.pop('unique_code_pool', None)
        super(UniqueCodePoolForm, self).__init__(*args, **kwargs)

        if self.unique_code_pool:
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
        store = self.user_api.unique_code_pool_store
        unique_code_pool = store.get_pool_by_name(pool_name)
        if unique_code_pool:
            raise forms.ValidationError(
                "A pool with the given name already exists.")

        return pool_name

    def import_vouchers(self):
        """Upload the unique codes and create a new unique code pool if one
        does not exist.
        """
        if not self.unique_code_pool:
            pool_name = self.cleaned_data['pool_name']
            config = {'ext_pool_name': self._make_ext_pool_name(pool_name)}
            store = self.user_api.unique_code_pool_store
            self.unique_code_pool = store.new_pool(pool_name, config,
                                                   imports=list())

        vouchers_file = self.cleaned_data['vouchers_file']
        import_unique_codes_file.delay(
            self.user_api.user_account_key,
            self.unique_code_pool.key,
            vouchers_file.name,
            vouchers_file.temporary_file_path(),
            vouchers_file.content_type)


class UniqueCodeQueryForm(BaseServiceForm, AjaxFormMixin):
    """Form used for querying unique codes"""

    messages = []

    query_string = forms.CharField(
        max_length=20, label=_("Enter the code or MSISDN"))

    def __init__(self, *args, **kwargs):
        self.unique_code_pool = kwargs.pop('unique_code_pool')
        super(UniqueCodeQueryForm, self).__init__(*args, **kwargs)
        self.messages = []

    def submit_query(self):
        """Query the voucher pool for the given code or MSISDN"""
        query_string = self.cleaned_data['query_string']
        voucher_service = self.service_def.voucher_service

        results = voucher_service.query_unique_code(
            self.unique_code_pool, query_string)

        if results:
            self.messages.append(
                _("The MSISDN associated with code '%(unique_code)s' is: "
                  "'%(msisdn)s'")
                % {'unique_code': query_string, 'msisdn': ''})

        else:
            results = voucher_service.query_msisdn(
                self.unique_code_pool, query_string)

        if results:
            self.messages.append(
                _("The code associated with MSISDN '%(msisdn)s' is: "
                  "'%(unique_code)s'")
                % {'msisdn': query_string, 'unique_code': ''})

        else:
            self.messages.append(
                _("'%(query_string)s' does not have an associated "
                  "code/MSISDN") % {'query_string': query_string})
