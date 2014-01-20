import os

from django.conf import settings
from django.core.urlresolvers import reverse
from django.core.files.uploadedfile import SimpleUploadedFile

from go.base.tests.helpers import GoDjangoTestCase

from go.services.vouchers.airtime.service import VoucherService
from go.services.vouchers.airtime.forms import VoucherPoolForm

from .helpers import ServiceViewHelper


class TestIndexView(GoDjangoTestCase):

    def setUp(self):
        self.service_helper = self.add_helper(ServiceViewHelper())
        self.client = self.service_helper.get_client()
        self.monkey_patch(VoucherService, 'total_vouchers',
                          self._total_vouchers)

    def _total_vouchers(self, voucher_pool):
        return 0

    def test_get_no_pools(self):
        url = reverse('services:service_index',
                      kwargs={'service_type': 'airtime'})

        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "You don't have any airtime yet.")

    def test_get_with_pool(self):
        voucher_pool = self.service_helper.create_voucher_pool()
        url = reverse('services:service_index',
                      kwargs={'service_type': 'airtime'})

        response = self.client.get(url)
        page = response.context[0].get('page')

        self.assertEqual(page.paginator.count, 1)
        self.assertEqual(page.object_list[0].name, voucher_pool.name)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "<td>test_pool</td>")


class TestAddVoucherPoolView(GoDjangoTestCase):

    def setUp(self):
        self.service_helper = self.add_helper(ServiceViewHelper())
        self.client = self.service_helper.get_client()
        self.monkey_patch(VoucherPoolForm, 'import_vouchers',
                          self._import_vouchers)

    def _import_vouchers(self):
        pass

    def test_get(self):
        url = reverse('services:service',
                      kwargs={'service_type': 'airtime',
                              'path_suffix': 'add'})

        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response, '<input class="form-control" id="id_pool_name" '
                      'maxlength="255" name="pool_name" type="text" />')

        self.assertContains(
            response, '<input class="form-control" id="id_vouchers_file" '
                      'name="vouchers_file" type="file" />')

    def test_post(self):
        csv_file = open(os.path.join(settings.PROJECT_ROOT, 'base',
                        'fixtures', 'sample-airtime-vouchers.csv'), 'rb')

        url = reverse('services:service',
                      kwargs={'service_type': 'airtime',
                              'path_suffix': 'add'})

        data = {
            'pool_name': 'test_pool',
            'vouchers_file': SimpleUploadedFile(
                csv_file.name, csv_file.read(), content_type='text/csv')
        }

        response = self.client.post(url, data)
        redirect_url = reverse('services:service_index',
                               kwargs={'service_type': 'airtime'})

        self.assertRedirects(response, redirect_url)


class TestImportVouchersView(GoDjangoTestCase):

    def setUp(self):
        self.service_helper = self.add_helper(ServiceViewHelper())
        self.client = self.service_helper.get_client()
        self.monkey_patch(VoucherPoolForm, 'import_vouchers',
                          self._import_vouchers)

        self.monkey_patch(VoucherService, 'total_vouchers',
                          self._total_vouchers)

    def _import_vouchers(self):
        pass

    def _total_vouchers(self, voucher_pool):
        return 0

    def test_get(self):
        voucher_pool = self.service_helper.create_voucher_pool()
        url = reverse('services:service',
                      kwargs={'service_type': 'airtime',
                              'path_suffix': 'import'})

        response = self.client.get(
            "%s?voucher_pool_key=%s" % (url, voucher_pool.key))

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response, '<input class="form-control" id="id_vouchers_file" '
                      'name="vouchers_file" type="file" />')

    def test_post(self):
        voucher_pool = self.service_helper.create_voucher_pool()
        csv_file = open(os.path.join(settings.PROJECT_ROOT, 'base',
                        'fixtures', 'sample-airtime-vouchers.csv'), 'rb')

        url = reverse('services:service',
                      kwargs={'service_type': 'airtime',
                              'path_suffix': 'import'})

        data = {
            'vouchers_file': SimpleUploadedFile(
                csv_file.name, csv_file.read(), content_type='text/csv')
        }

        response = self.client.post(
            "%s?voucher_pool_key=%s" % (url, voucher_pool.key), data)

        redirect_url = reverse('services:service_index',
                               kwargs={'service_type': 'airtime'})

        self.assertRedirects(response, redirect_url)


class TestExportVouchersView(GoDjangoTestCase):

    def setUp(self):
        self.service_helper = self.add_helper(ServiceViewHelper())
        self.client = self.service_helper.get_client()
        self.monkey_patch(VoucherService, 'export_vouchers',
                          self._export_vouchers)

    def _export_vouchers(self, voucher_pool):
        return [{
            'operator': 'Tank',
            'denomination': 'red',
            'voucher': 'Tr0'
        }, {
            'operator': 'Tank',
            'denomination': 'blue',
            'voucher': 'Tb0'
        }, {
            'operator': 'Tank',
            'denomination': 'green',
            'voucher': 'Tg0'
        }]

    def test_get(self):
        voucher_pool = self.service_helper.create_voucher_pool()
        url = reverse('services:service',
                      kwargs={'service_type': 'airtime',
                              'path_suffix': 'export'})

        response = self.client.get(
            "%s?voucher_pool_key=%s" % (url, voucher_pool.key))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, 'operator,denomination,voucher\r\n'
                                           'Tank,red,Tr0\r\n'
                                           'Tank,blue,Tb0\r\n'
                                           'Tank,green,Tg0\r\n')


class QueryVouchersView(GoDjangoTestCase):

    def setUp(self):
        self.service_helper = self.add_helper(ServiceViewHelper())
        self.client = self.service_helper.get_client()
        self.monkey_patch(VoucherService, 'query_msisdn',
                          self._query_msisdn)

    def _query_msisdn(self, voucher_pool, msisdn):
        return [{
            'response_data': {
                'voucher': 'Tr0'
            }
        }]

    def test_get(self):
        voucher_pool = self.service_helper.create_voucher_pool()
        url = reverse('services:service',
                      kwargs={'service_type': 'airtime',
                              'path_suffix': 'query'})

        response = self.client.get(
            "%s?voucher_pool_key=%s" % (url, voucher_pool.key))

        print response.content
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response, '<input class="form-control" id="id_msisdn" '
                      'maxlength="20" name="msisdn" type="text" />')

    def test_post(self):
        voucher_pool = self.service_helper.create_voucher_pool()
        url = reverse('services:service',
                      kwargs={'service_type': 'airtime',
                              'path_suffix': 'query'})

        data = {'msisdn': '12345'}
        response = self.client.post(
            "%s?voucher_pool_key=%s" % (url, voucher_pool.key), data)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "The airtime voucher associated with "
                                      "MSISDN '12345' is 'Tr0'.")
