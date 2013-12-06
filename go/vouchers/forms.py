import re
import csv
import requests
import xlrd
import StringIO

from hashlib import md5

from django import forms

from go.vouchers.models import AirtimeVoucherPool

API_URL = 'http://127.0.0.1:8888'


class AirtimeVoucherPoolForm(forms.ModelForm):
    """``ModelForm`` for ``go.vouchers.models.AirtimeVoucherPool``"""

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
        self.fields['pool_name'].label = \
            "Provide a name for your airtime voucher pool"

    def clean_vouchers_file(self):
        """Ensure that the uploaded file is either a CSV file or an Excel
        spreadsheet and validate the file format.
        """
        vouchers_file = self.cleaned_data['vouchers_file']
        excel_content_types = [
            'application/vnd.ms-excel',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        ]
        csv_content_types = [
            'text/csv'
        ]
        if vouchers_file.content_type in csv_content_types:
            # Validate the CSV file format and read its contents
            csvfile = StringIO.StringIO(vouchers_file.read())
            reader = csv.reader(csvfile)
            row = reader.next()
            if (len(row) < 3 or row[0] != 'operator'
                    or row[1] != 'denomination' or row[2] != 'voucher'):
                raise forms.ValidationError(
                    "Invalid file format.")

            self.file_content = csvfile.getvalue()

        elif vouchers_file.content_type in excel_content_types:
            # Validate the Excel spreadsheet format and read its contents
            book = xlrd.open_workbook(file_contents=vouchers_file.read())
            sheets = book.sheets()
            if not sheets:
                raise forms.ValidationError(
                    "The file is empty.")

            first_sheet = sheets[0]
            if (first_sheet.cell(0, 0).value != 'operator'
                    or first_sheet.cell(0, 1).value != 'denomination'
                    or first_sheet.cell(0, 2).value != 'voucher'):
                raise forms.ValidationError(
                    "Invalid file format.")

            csvfile = StringIO.StringIO()
            writer = csv.writer(csvfile)
            for row in xrange(0, first_sheet.nrows):
                writer.writerow([
                    first_sheet.cell(row, 0).value,
                    first_sheet.cell(row, 1).value,
                    first_sheet.cell(row, 2).value])

            self.file_content = csvfile.getvalue()
            csvfile.close()

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

    def _upload_vouchers(self, pool_name):
        """Upload the vouchers to the Airtime Voucher service"""
        content_md5 = md5(self.file_content).hexdigest().lower()
        url = '%s/%s/import/req-0' % (API_URL, pool_name)
        headers = {'Content-MD5': content_md5}
        requests.put(url, self.file_content, headers=headers)
        # TODO: Validate service response

    def save(self, *args, **kwargs):
        """Upload the vouchers and create a new Airtime Voucher pool if one
        does not exist.
        """
        kwargs['commit'] = False
        airtime_voucher_pool = super(AirtimeVoucherPoolForm, self).save(
            *args, **kwargs)

        pool_name = self.cleaned_data.get('pool_name')
        ext_pool_name = self._make_ext_pool_name(pool_name)
        self._upload_vouchers(ext_pool_name)

        airtime_voucher_pool.user = self.user
        airtime_voucher_pool.ext_pool_name = ext_pool_name
        airtime_voucher_pool.save()

        return airtime_voucher_pool
