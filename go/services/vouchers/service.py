from uuid import uuid4


class VoucherServiceError(Exception):
    """Raised when an error occurs with the voucher service"""


class BaseVoucherService(object):
    """Base class for voucher service proxies"""

    def _is_success(self, response):
        """Return `True` if the HTTP response code is either 200 (OK)
        or 201 (Created), `False` otherwise."""
        return response.status_code in [200, 201]

    def _is_json(self, response):
        """Return `True` if the HTTP response contains JSON,
           `False` otherwise."""
        return 'application/json' in response.headers.get('content-type',
                                                          None)

    def _get_result(self, response):
        """Return the response content.

        - If there was an error raise
          ``go.services.vouchers.service.VoucherServiceError``

        - If the content type is `application/json`, return a Python `dict`
        """
        is_success = self._is_success(response)
        if self._is_json(response):
            result = response.json
            if not is_success:
                error = result.get('error', response.text)
                raise VoucherServiceError(error)
        else:
            result = response.text
            if not is_success:
                raise VoucherServiceError(result)
        return result

    def make_request_id(self):
        """Return a new request ID"""
        return uuid4().get_hex()
