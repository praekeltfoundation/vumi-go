import requests
import json

from hashlib import md5
from urlparse import urljoin

from go.vouchers import settings
from go.vouchers.models import BulkImport


class VoucherServiceError(Exception):
    """Raised when an error occurs with the voucher service"""


class BaseVoucherService(object):
    """Base class for voucher service proxies"""

    _instance = None

    def __new__(cls, *args, **kwargs):
        """Singleton implementation"""
        if not isinstance(cls._instance, cls):
            cls._instance = object.__new__(cls, *args, **kwargs)
        return cls._instance

    def _is_success(self, response):
        """Return `True` if the HTTP response code is either 200 (OK)
        or 201 (Created), `False` otherwise."""
        return response.status_code in [200, 201]

    def _get_result(self, response):
        """Return the response content.

        - If there was an error raise
          ``go.vouchers.services.VoucherServiceError``

        - If the content type is `application/json`, return a Python `dict`

        """
        failed = not self._is_success(response)
        content_type = response.headers.get('content-type', None)
        if 'application/json' in content_type:
            result = response.json
            if failed:
                error = result.get('error', response.text)
                raise VoucherServiceError(error)
        else:
            result = response.text
            if failed:
                raise VoucherServiceError(result)
        return result


class AirtimeVoucherService(BaseVoucherService):
    """Airtime Voucher Service proxy"""

    def import_vouchers(self, voucher_pool, filename, content):
        """Import the vouchers `content` into the given `voucher_pool`"""
        bulk_import = voucher_pool.imports.create(filename=filename)
        request_id = 'req-%d' % (bulk_import.id,)
        url = urljoin(settings.AIRTIME_VOUCHER_SERVICE_URL,
                      '%s/import/%s' % (voucher_pool.ext_pool_name,
                                        request_id))

        content_md5 = md5(content).hexdigest().lower()
        headers = {'Content-MD5': content_md5}
        response = requests.put(url, content, headers=headers)

        try:
            self._get_result(response)
            bulk_import.status = BulkImport.STATUS_COMPLETED
            bulk_import.save()

        except VoucherServiceError as error:
            bulk_import.status = BulkImport.STATUS_FAILED
            bulk_import.save()
            raise error

    def voucher_counts(self, voucher_pool):
        """Return voucher counts for the given `voucher_pool`"""
        url = urljoin(settings.AIRTIME_VOUCHER_SERVICE_URL,
                      '%s/voucher_counts' % (voucher_pool.ext_pool_name,))

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
        voucher_list = []
        for bulk_import in voucher_pool.imports.all():
            request_id = 'req-%d' % (bulk_import.id,)
            url = urljoin(settings.AIRTIME_VOUCHER_SERVICE_URL,
                          '%s/export/%s' % (voucher_pool.ext_pool_name,
                                            request_id))

            response = requests.put(url, data=json.dumps({}))
            result = self._get_result(response)
            voucher_list.extend(result.get('vouchers', []))
        return voucher_list

    def audit_query(self, voucher_pool, msisdn):
        """Return all vouchers for the given `voucher_pool`"""
        url = urljoin(settings.AIRTIME_VOUCHER_SERVICE_URL,
                      '%s/audit_query' % (voucher_pool.ext_pool_name,))

        params = {'field': 'user_id', 'value': msisdn}
        response = requests.get(url, params=params)
        result = self._get_result(response)
        return result.get('results', [])


class UniqueCodeService(BaseVoucherService):
    """Unique Code Service proxy"""
    pass
