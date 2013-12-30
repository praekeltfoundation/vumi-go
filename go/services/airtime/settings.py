from django.conf import settings

SERVICE_URL = getattr(settings, 'AIRTIME_VOUCHER_SERVICE_URL',
                      'http://127.0.0.1:8888')

FILE_FORMAT = ('operator', 'denomination', 'voucher')

VOUCHER_POOLS_PER_PAGE = getattr(
    settings, 'AIRTIME_VOUCHER_POOLS_PER_PAGE', 25)
