import re

from django import forms

from go.services import settings as app_settings
from go.services.forms import AjaxFormMixin, BaseServiceForm
from go.services.vouchers.parsers import ExcelParser, CsvParser


class BaseVoucherPoolForm(BaseServiceForm, AjaxFormMixin):
    """Base class for a voucher pool form"""

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
        if vouchers_file.content_type in CsvParser.CONTENT_TYPES:
            self._validate_csv_format()

        elif vouchers_file.content_type in ExcelParser.CONTENT_TYPES:
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

    def import_vouchers(self):
        """Import the vouchers into the voucher pool.

        If the voucher pool does not yet exist create a new one.
        """
        raise NotImplementedError()
