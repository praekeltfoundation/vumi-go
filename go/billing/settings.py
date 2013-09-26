from django.conf import settings

CREDIT_CONVERSION_FACTOR = getattr(
    settings, 'BILLING_CREDIT_CONVERSION_FACTOR', 40.0)

API_MIN_CONNECTIONS = getattr(settings, 'BILLING_API_MIN_CONNECTIONS', 10)

ENDPOINT_DESCRIPTION_STRING = getattr(
    settings, 'BILLING_ENDPOINT_DESCRIPTION_STRING',
    "tcp:9090:interface=127.0.0.1")


def get_connection_string():
    """Return the database connection string"""
    return "host='%s' dbname='%s' user='%s' password='%s'" \
        % (settings.DATABASES['default'].get('HOST', 'localhost'),
           settings.DATABASES['default'].get('NAME'),
           settings.DATABASES['default'].get('USER'),
           settings.DATABASES['default'].get('PASSWORD'))
