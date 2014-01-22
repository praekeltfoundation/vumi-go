import requests

from mock import patch
from hashlib import md5
from urlparse import urljoin

from go.base.tests.helpers import GoDjangoTestCase

from go.services.vouchers.service import BaseVoucherService

from go.services.vouchers.airtime import settings
from go.services.vouchers.airtime.service import VoucherService

from .helpers import ServiceViewHelper


class TestVoucherService(GoDjangoTestCase):

    def setUp(self):
        self.service_helper = self.add_helper(ServiceViewHelper())
        self.voucher_service = VoucherService()
        self.monkey_patch(BaseVoucherService, 'make_request_id',
                          self._make_request_id)

        self.monkey_patch(BaseVoucherService, '_get_result',
                          self._get_result)

    def _make_request_id(self):
        return "req-0"

    def _get_result(self, response):
        return {}

    @patch.object(requests, 'put')
    def test_import_vouchers(self, mock_method):
        voucher_pool = self.service_helper.create_voucher_pool()
        content = 'operator,denomination,voucher\r\nTank,red,Tr0\r\n'
        'Tank,blue,Tb0\r\nTank,green,Tg0\r\n'

        self.voucher_service.import_vouchers(voucher_pool, content)

        url = urljoin(settings.SERVICE_URL,
                      '%s/import/%s' % (voucher_pool.config['ext_pool_name'],
                                        'req-0'))

        content_md5 = md5(content).hexdigest().lower()
        headers = {'Content-MD5': content_md5}

        mock_method.assert_called_with(url, content, headers=headers)

    @patch.object(requests, 'get')
    def test_voucher_counts(self, mock_method):
        voucher_pool = self.service_helper.create_voucher_pool()
        self.voucher_service.voucher_counts(voucher_pool)

        url = urljoin(settings.SERVICE_URL,
                      '%s/voucher_counts' %
                      (voucher_pool.config['ext_pool_name'],))

        mock_method.assert_called_with(url)

    @patch.object(requests, 'put')
    def test_export_vouchers(self, mock_method):
        voucher_pool = self.service_helper.create_voucher_pool(
            imports=[u'req-1'])

        self.voucher_service.export_vouchers(voucher_pool)

        url = urljoin(settings.SERVICE_URL,
                      '%s/export/%s' %
                      (voucher_pool.config['ext_pool_name'], u'req-1'))

        mock_method.assert_called_with(url, data='{}')

    @patch.object(requests, 'get')
    def test_query_msisdn(self, mock_method):
        voucher_pool = self.service_helper.create_voucher_pool()
        msisdn = '12345'

        self.voucher_service.query_msisdn(voucher_pool, msisdn)

        url = urljoin(settings.SERVICE_URL,
                      '%s/audit_query' %
                      (voucher_pool.config['ext_pool_name'],))

        params = {'field': 'user_id', 'value': msisdn}
        mock_method.assert_called_with(url, params=params)
