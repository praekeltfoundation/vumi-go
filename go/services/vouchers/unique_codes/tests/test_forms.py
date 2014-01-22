import os

from django.conf import settings

from go.base.tests.helpers import GoDjangoTestCase

from go.services.definition import ServiceDefinitionBase
from go.services.vouchers.unique_codes.forms import UniqueCodePoolForm
from go.services.vouchers.unique_codes.tasks import import_unique_codes_file

from go.services.tests.helpers import FakeUploadedFile

from .helpers import ServiceViewHelper


class DummyServiceDefinition(ServiceDefinitionBase):

    service_type = u"dummy_service"
    service_display_name = u"Dummy service"


class TestUniqueCodePool(GoDjangoTestCase):

    def setUp(self):
        self.service_helper = self.add_helper(ServiceViewHelper())
        self.service_def = DummyServiceDefinition()
        self.monkey_patch(import_unique_codes_file, 'delay',
                          self._import_unique_codes_file)

    def _import_unique_codes_file(self, *args):
        self.import_unique_codes_file_args = args

    def test_import_csv_file(self):
        file_name = os.path.join(settings.PROJECT_ROOT, 'base', 'fixtures',
                                 'sample-unique-codes.csv')

        with open(file_name, 'rb') as csv_file:
            form_data = {
                'pool_name': 'test_pool',
            }

            form_files = {
                'vouchers_file': FakeUploadedFile(
                    csv_file, content_type='text/csv')
            }

            user_api = self.service_helper.get_user_api()
            form = UniqueCodePoolForm(form_data, form_files,
                                      service_def=self.service_def,
                                      user_api=user_api)

            self.assertTrue(form.is_valid())

    def test_import_xls_file(self):
        file_name = os.path.join(settings.PROJECT_ROOT, 'base', 'fixtures',
                                 'sample-unique-codes.xls')

        with open(file_name, 'rb') as csv_file:
            form_data = {
                'pool_name': 'test_pool',
            }

            form_files = {
                'vouchers_file': FakeUploadedFile(
                    csv_file, content_type='application/vnd.ms-excel')
            }

            user_api = self.service_helper.get_user_api()
            form = UniqueCodePoolForm(form_data, form_files,
                                      service_def=self.service_def,
                                      user_api=user_api)

            self.assertTrue(form.is_valid())

    def test_import_invalid_file(self):
        file_name = os.path.join(settings.PROJECT_ROOT, 'base', 'fixtures',
                                 'sample-unique-codes-invalid.csv')

        with open(file_name, 'rb') as csv_file:
            form_data = {
                'pool_name': 'test_pool',
            }

            form_files = {
                'vouchers_file': FakeUploadedFile(
                    csv_file, content_type='text/csv')
            }

            user_api = self.service_helper.get_user_api()
            form = UniqueCodePoolForm(form_data, form_files,
                                      service_def=self.service_def,
                                      user_api=user_api)

            self.assertEqual(form.is_valid(), False)

    def test_import_vouchers(self):
        unique_code_pool = self.service_helper.create_unique_code_pool()
        file_name = os.path.join(settings.PROJECT_ROOT, 'base', 'fixtures',
                                 'sample-unique-codes.csv')

        with open(file_name, 'rb') as csv_file:
            form_files = {
                'vouchers_file': FakeUploadedFile(
                    csv_file, content_type='text/csv')
            }

            user_api = self.service_helper.get_user_api()
            form = UniqueCodePoolForm({}, form_files,
                                      service_def=self.service_def,
                                      user_api=user_api,
                                      unique_code_pool=unique_code_pool)

            self.assertTrue(form.is_valid())
            form.import_vouchers()
            expected_args = (user_api.user_account_key,
                             unique_code_pool.key,
                             os.path.basename(csv_file.name),
                             csv_file.name,
                             'text/csv')

            self.assertEqual(self.import_unique_codes_file_args,
                             expected_args)
