import requests
import json

from hashlib import md5
from urlparse import urljoin

from go.services.vouchers.service import BaseVoucherService
from go.services.vouchers.airtime import settings as service_settings


class VoucherService(BaseVoucherService):
    """Airtime Voucher service proxy"""

    def import_vouchers(self, voucher_pool, content):
        """Import the vouchers `content` into the given `voucher_pool`"""
        pool_name = voucher_pool.config['ext_pool_name']
        request_id = self.make_request_id()
        url = urljoin(service_settings.SERVICE_URL,
                      '%s/import/%s' % (pool_name, request_id))

        content_md5 = md5(content).hexdigest().lower()
        headers = {'Content-MD5': content_md5}
        response = requests.put(url, content, headers=headers)
        self._get_result(response)
        voucher_pool.imports.append(unicode(request_id))
        voucher_pool.save()

    def voucher_counts(self, voucher_pool):
        """Return voucher counts for the given `voucher_pool`"""
        pool_name = voucher_pool.config['ext_pool_name']
        url = urljoin(service_settings.SERVICE_URL,
                      '%s/voucher_counts' % (pool_name,))

        response = requests.get(url)
        result = self._get_result(response)
        return result.get('voucher_counts', [])

    def total_vouchers(self, voucher_pool):
        """Return the total number of vouchers in the given `voucher_pool`"""
        voucher_counts = self.voucher_counts(voucher_pool)
        total_vouchers = 0
        for voucher in voucher_counts:
            total_vouchers += voucher.get('count', 0)
        return total_vouchers

    def export_vouchers(self, voucher_pool):
        """Return all vouchers for the given `voucher_pool`"""
        pool_name = voucher_pool.config['ext_pool_name']
        voucher_list = []
        for request_id in voucher_pool.imports:
            url = urljoin(service_settings.SERVICE_URL,
                          '%s/export/%s' % (pool_name, request_id))

            response = requests.put(url, data=json.dumps({}))
            result = self._get_result(response)
            voucher_list.extend(result.get('vouchers', []))
        return voucher_list

    def query_msisdn(self, voucher_pool, msisdn):
        """Return all vouchers in the given `voucher_pool` that match the
        given `msisdn`.
        """
        pool_name = voucher_pool.config['ext_pool_name']
        url = urljoin(service_settings.SERVICE_URL,
                      '%s/audit_query' % (pool_name,))

        params = {'field': 'user_id', 'value': msisdn}
        response = requests.get(url, params=params)
        result = self._get_result(response)
        return result.get('results', [])
