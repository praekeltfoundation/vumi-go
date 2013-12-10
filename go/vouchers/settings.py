from django.conf import settings

AIRTIME_VOUCHER_SERVICE_URL = getattr(
    settings, 'VOUCHERS_AIRTIME_VOUCHER_SERVICE_URL',
    'http://127.0.0.1:8888')

AIRTIME_VOUCHER_FILE_FORMAT = ('operator', 'denomination', 'voucher')

UNIQUE_CODE_SERVICE_URL = getattr(
    settings, 'VOUCHERS_UNIQUE_CODE_SERVICE_URL',
    'http://127.0.0.1:7777')

REQUEST_RECORD_LIMIT = getattr(
    settings, 'VOUCHERS_REQUEST_RECORD_LIMIT', 10000)
