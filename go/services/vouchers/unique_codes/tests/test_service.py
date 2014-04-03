import requests

from mock import patch
from hashlib import md5
from urlparse import urljoin

from go.base.tests.helpers import GoDjangoTestCase

from go.services.vouchers.service import BaseVoucherService

from go.services.vouchers.unique_codes import settings
from go.services.vouchers.unique_codes.service import UniqueCodeService

from .helpers import ServiceViewHelper


class TestVoucherService(GoDjangoTestCase):

    def setUp(self):
        self.service_helper = self.add_helper(ServiceViewHelper())
        self.unique_code_service = UniqueCodeService()
        self.monkey_patch(BaseVoucherService, 'make_request_id',
                          self._make_request_id)

        self.monkey_patch(BaseVoucherService, '_get_result',
                          self._get_result)

    def _make_request_id(self):
        return "req-0"

    def _get_result(self, response):
        return {}

    @patch.object(requests, 'put')
    def test_import_unique_codes(self, mock_method):
        unique_code_pool = self.service_helper.create_unique_code_pool()
        content = 'unique_code,flavour\n\rvanilla0,vanilla\n\rvanilla1,'
        'vanilla\n\rchocolate0,chocolate\n\rchocolate1,chocolate'

        self.unique_code_service.import_unique_codes(
            unique_code_pool, content)

        url = urljoin(settings.SERVICE_URL,
                      '%s/import/%s' %
                      (unique_code_pool.config['ext_pool_name'], 'req-0'))

        content_md5 = md5(content).hexdigest().lower()
        headers = {'Content-MD5': content_md5}

        mock_method.assert_called_with(url, content, headers=headers)

    @patch.object(requests, 'get')
    def test_unique_code_counts(self, mock_method):
        unique_code_pool = self.service_helper.create_unique_code_pool()

        self.unique_code_service.unique_code_counts(unique_code_pool)

        url = urljoin(settings.SERVICE_URL,
                      '%s/unique_code_counts' %
                      (unique_code_pool.config['ext_pool_name'],))

        mock_method.assert_called_with(url)

    @patch.object(requests, 'get')
    def test_query_unique_code(self, mock_method):
        unique_code_pool = self.service_helper.create_unique_code_pool()
        unique_code = 'vanilla0'

        self.unique_code_service.query_unique_code(unique_code_pool, unique_code)

        url = urljoin(settings.SERVICE_URL,
                      '%s/audit_query' %
                      (unique_code_pool.config['ext_pool_name'],))

        params = {'field': 'unique_code', 'value': unique_code}
        mock_method.assert_called_with(url, params=params)

    @patch.object(requests, 'get')
    def test_query_msisdn(self, mock_method):
        unique_code_pool = self.service_helper.create_unique_code_pool()
        msisdn = '0821234567'

        self.unique_code_service.query_msisdn(unique_code_pool, msisdn)

        url = urljoin(settings.SERVICE_URL,
                      '%s/audit_query' %
                      (unique_code_pool.config['ext_pool_name'],))

        params = {'field': 'user_id', 'value': msisdn}
        mock_method.assert_called_with(url, params=params)
