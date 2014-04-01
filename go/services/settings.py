from django.conf import settings

VOUCHER_POOL_PREFIX = getattr(settings, 'GO_VOUCHER_POOL_PREFIX', 'go_')
