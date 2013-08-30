from django.conf import settings

CREDIT_CONVERSION_FACTOR = getattr(
    settings, 'BILLING_CREDIT_CONVERSION_FACTOR', 40.0)

API_MIN_CONNECTIONS = getattr(settings, 'BILLING_API_MIN_CONNECTIONS', 10)

DEFAULT_API_CONNECTION_STRING = \
    "host='%s' dbname='%s' user='%s' password='%s'" \
    % (settings.DATABASES['default'].get('HOST', 'localhost'),
       settings.DATABASES['default'].get('NAME'),
       settings.DATABASES['default'].get('USER'),
       settings.DATABASES['default'].get('PASSWORD'))

API_CONNECTION_STRING = getattr(
    settings, 'BILLING_API_CONNECTION_STRING', DEFAULT_API_CONNECTION_STRING)
