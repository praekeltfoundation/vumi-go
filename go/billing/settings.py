from django.conf import settings
from django.contrib.auth import get_user_model

CREDIT_CONVERSION_FACTOR = getattr(
    settings, 'BILLING_CREDIT_CONVERSION_FACTOR', 0.4)

API_MIN_CONNECTIONS = getattr(settings, 'BILLING_API_MIN_CONNECTIONS', 10)

ENDPOINT_DESCRIPTION_STRING = getattr(
    settings, 'BILLING_ENDPOINT_DESCRIPTION_STRING',
    "tcp:9090:interface=127.0.0.1")


def get_user_table():
    """Return the name of the table used by the user model."""
    user_model = get_user_model()
    return user_model._meta.db_table


def get_connection_string():
    """Return the database connection string"""
    db = settings.DATABASES['default']
    if 'postgres' not in db['ENGINE']:
        raise ValueError("Billing API only supports PostGreSQL.")
    return "host='%s' dbname='%s' user='%s' password='%s'" \
        % (db.get('HOST', 'localhost'), db.get('NAME'), db.get('USER'),
           db.get('PASSWORD'))
