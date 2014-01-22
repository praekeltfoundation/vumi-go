import requests

from hashlib import md5
from urlparse import urljoin

from go.services.vouchers.service import BaseVoucherService
from go.services.vouchers.unique_codes import settings as service_settings


class UniqueCodeService(BaseVoucherService):
    """Unique Code service proxy"""

    def import_unique_codes(self, unique_code_pool, content):
        """Import the unique codes `content` into the given
        `unique_code_pool`.
        """
        pool_name = unique_code_pool.config['ext_pool_name']
        request_id = self.make_request_id()
        url = urljoin(service_settings.SERVICE_URL,
                      '%s/import/%s' % (pool_name, request_id))

        content_md5 = md5(content).hexdigest().lower()
        headers = {'Content-MD5': content_md5}
        response = requests.put(url, content, headers=headers)
        self._get_result(response)

        unique_code_pool.imports.append(unicode(request_id))
        unique_code_pool.save()

    def unique_code_counts(self, unique_code_pool):
        """Return unique code counts for the given `unique_code_pool`"""
        pool_name = unique_code_pool.config['ext_pool_name']
        url = urljoin(service_settings.SERVICE_URL,
                      '%s/unique_code_counts' % (pool_name,))

        response = requests.get(url)
        result = self._get_result(response)
        return result.get('unique_code_counts', [])

    def total_unique_codes(self, unique_code_pool):
        """Return the total number of unique codes in the given
        `unique_code_pool`.
        """
        unique_code_counts = self.unique_code_counts(unique_code_pool)
        total_unique_codes = 0
        for unique_code in unique_code_counts:
            total_unique_codes += unique_code.get('count', 0)
        return total_unique_codes

    def query_unique_code(self, unique_code_pool, unique_code):
        """Return all unique codes matching the given `unique_code`"""
        pool_name = unique_code_pool.config['ext_pool_name']
        url = urljoin(service_settings.SERVICE_URL,
                      '%s/audit_query' % (pool_name,))

        params = {'field': 'unique_code', 'value': unique_code}
        response = requests.get(url, params=params)
        result = self._get_result(response)
        return result.get('results', [])

    def query_msisdn(self, unique_code_pool, msisdn):
        """Return all unique codes matching the given `msisdn`"""
        pool_name = unique_code_pool.config['ext_pool_name']
        url = urljoin(service_settings.SERVICE_URL,
                      '%s/audit_query' % (pool_name,))

        params = {'field': 'user_id', 'value': msisdn}
        response = requests.get(url, params=params)
        result = self._get_result(response)
        return result.get('results', [])
