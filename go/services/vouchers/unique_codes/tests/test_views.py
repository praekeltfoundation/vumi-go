import os

from django.conf import settings
from django.core.urlresolvers import reverse
from go.base.tests.helpers import GoDjangoTestCase

from go.services.vouchers.unique_codes.service import UniqueCodeService
from go.services.vouchers.unique_codes.forms import UniqueCodePoolForm

from go.services.tests.helpers import FakeUploadedFile

from .helpers import ServiceViewHelper


class TestIndexView(GoDjangoTestCase):

    def setUp(self):
        self.service_helper = self.add_helper(ServiceViewHelper())
        self.client = self.service_helper.get_client()
        self.monkey_patch(UniqueCodeService, 'total_unique_codes',
                          self._total_unique_codes)

    def _total_unique_codes(self, unique_code_pool):
        return 0

    def test_get_no_pools(self):
        url = reverse('services:service_index',
                      kwargs={'service_type': 'unique_codes'})

        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "You don't have any unique codes yet.")

    def test_get_with_pool(self):
        unique_code_pool = self.service_helper.create_unique_code_pool()
        url = reverse('services:service_index',
                      kwargs={'service_type': 'unique_codes'})

        response = self.client.get(url)
        page = response.context[0].get('page')

        self.assertEqual(page.paginator.count, 1)
        self.assertEqual(page.object_list[0].name, unique_code_pool.name)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "<td>test_pool</td>")


class TestAddUniqueCodePoolView(GoDjangoTestCase):

    def setUp(self):
        self.service_helper = self.add_helper(ServiceViewHelper())
        self.client = self.service_helper.get_client()
        self.monkey_patch(UniqueCodePoolForm, 'import_vouchers',
                          self._import_vouchers)

    def _import_vouchers(self):
        pass

    def test_get(self):
        url = reverse('services:service',
                      kwargs={'service_type': 'unique_codes',
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
        file_name = os.path.join(settings.PROJECT_ROOT, 'base', 'fixtures',
                                 'sample-unique-codes.csv')

        with open(file_name, 'rb') as csv_file:
            url = reverse('services:service',
                          kwargs={'service_type': 'unique_codes',
                                  'path_suffix': 'add'})

            data = {
                'pool_name': 'test_pool',
                'vouchers_file': FakeUploadedFile(
                    csv_file, content_type='text/csv')
            }

            response = self.client.post(url, data)
            redirect_url = reverse('services:service_index',
                                   kwargs={'service_type': 'unique_codes'})

            self.assertRedirects(response, redirect_url)


class TestImportUniqueCodesView(GoDjangoTestCase):

    def setUp(self):
        self.service_helper = self.add_helper(ServiceViewHelper())
        self.client = self.service_helper.get_client()
        self.monkey_patch(UniqueCodePoolForm, 'import_vouchers',
                          self._import_vouchers)

        self.monkey_patch(UniqueCodeService, 'total_unique_codes',
                          self._total_unique_codes)

    def _import_vouchers(self):
        pass

    def _total_unique_codes(self, unique_code_pool):
        return 0

    def test_get(self):
        unique_code_pool = self.service_helper.create_unique_code_pool()
        url = reverse('services:service',
                      kwargs={'service_type': 'unique_codes',
                              'path_suffix': 'import'})

        response = self.client.get(
            "%s?unique_code_pool_key=%s" % (url, unique_code_pool.key))

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response, '<input class="form-control" id="id_vouchers_file" '
                      'name="vouchers_file" type="file" />')

    def test_post(self):
        unique_code_pool = self.service_helper.create_unique_code_pool()

        file_name = os.path.join(settings.PROJECT_ROOT, 'base', 'fixtures',
                                 'sample-unique-codes.csv')

        with open(file_name, 'rb') as csv_file:
            url = reverse('services:service',
                          kwargs={'service_type': 'unique_codes',
                                  'path_suffix': 'import'})

            data = {
                'vouchers_file': FakeUploadedFile(csv_file,
                                                  content_type='text/csv')
            }

            response = self.client.post(
                "%s?unique_code_pool_key=%s" %
                (url, unique_code_pool.key), data)

            redirect_url = reverse('services:service_index',
                                   kwargs={'service_type': 'unique_codes'})

            self.assertRedirects(response, redirect_url)


class TestQueryUniqueCodesView(GoDjangoTestCase):

    def setUp(self):
        self.service_helper = self.add_helper(ServiceViewHelper())
        self.client = self.service_helper.get_client()

    def _query_msisdn(self, unique_code_pool, msisdn):
        return [{'response_data': {'unique_code': 'vanilla0'}}]

    def _query_msisdn_no_result(self, unique_code_pool, msisdn):
        return []

    def _query_unique_code(self, unique_code_pool, unique_code):
        return [{'response_data': {'user_id': '0821234567'}}]

    def _query_unique_code_no_result(self, unique_code_pool, unique_code):
        return []

    def test_get(self):
        unique_code_pool = self.service_helper.create_unique_code_pool()
        url = reverse('services:service',
                      kwargs={'service_type': 'unique_codes',
                              'path_suffix': 'query'})

        response = self.client.get(
            "%s?unique_code_pool_key=%s" % (url, unique_code_pool.key))

        print response.content
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response, '<input class="form-control" id="id_query_string" '
                      'maxlength="20" name="query_string" type="text" />')

    def test_post_unique_code(self):
        self.monkey_patch(UniqueCodeService, 'query_msisdn',
                          self._query_msisdn_no_result)

        self.monkey_patch(UniqueCodeService, 'query_unique_code',
                          self._query_unique_code)

        unique_code_pool = self.service_helper.create_unique_code_pool()
        url = reverse('services:service',
                      kwargs={'service_type': 'unique_codes',
                              'path_suffix': 'query'})

        data = {'query_string': 'vanilla0'}
        response = self.client.post(
            "%s?unique_code_pool_key=%s" %
            (url, unique_code_pool.key), data)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "The MSISDN associated with code "
                                      "'vanilla0' is: '0821234567'")

    def test_post_msisdn(self):
        self.monkey_patch(UniqueCodeService, 'query_msisdn',
                          self._query_msisdn)

        self.monkey_patch(UniqueCodeService, 'query_unique_code',
                          self._query_unique_code_no_result)

        unique_code_pool = self.service_helper.create_unique_code_pool()
        url = reverse('services:service',
                      kwargs={'service_type': 'unique_codes',
                              'path_suffix': 'query'})

        data = {'query_string': '0821234567'}
        response = self.client.post(
            "%s?unique_code_pool_key=%s" %
            (url, unique_code_pool.key), data)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "The code associated with MSISDN "
                                      "'0821234567' is: 'vanilla0'")

    def test_post_no_result(self):
        self.monkey_patch(UniqueCodeService, 'query_msisdn',
                          self._query_msisdn_no_result)

        self.monkey_patch(UniqueCodeService, 'query_unique_code',
                          self._query_unique_code_no_result)

        unique_code_pool = self.service_helper.create_unique_code_pool()
        url = reverse('services:service',
                      kwargs={'service_type': 'unique_codes',
                              'path_suffix': 'query'})

        data = {'query_string': 'invalid'}
        response = self.client.post(
            "%s?unique_code_pool_key=%s" %
            (url, unique_code_pool.key), data)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "'invalid' does not have an associated "
                                      "code/MSISDN")
