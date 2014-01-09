from django.conf import settings

DEFAULT_INSTALLED_SERVICES = {
    'go.services.vouchers.airtime': {
        'namespace': 'airtime',
        'display_name': 'Airtime vouchers',
    },
    'go.services.vouchers.unique_codes': {
        'namespace': 'unique_codes',
        'display_name': 'Unique codes',
    },
}

INSTALLED_SERVICES = getattr(settings, 'INSTALLED_SERVICES',
                             DEFAULT_INSTALLED_SERVICES)

VOUCHER_POOL_PREFIX = getattr(settings, 'GO_VOUCHER_POOL_PREFIX', 'go_')
