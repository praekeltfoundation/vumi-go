from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model

from go.config import billing_quantization_exponent

# 10 credits = 1 US cent
CREDIT_CONVERSION_FACTOR = getattr(
    settings, 'BILLING_CREDIT_CONVERSION_FACTOR', Decimal('10.00'))

# This is currently pulled in from `go.config` to avoid pulling a pile of
# Django stuff into `go.vumitools.billing_worker` through `go.billing.utils`.
QUANTIZATION_EXPONENT = billing_quantization_exponent()
if hasattr(settings, 'BILLING_QUANTIZATION_EXPONENT'):
    raise ValueError(
        "BILLING_QUANTIZATION_EXPONENT cannot be configured in settings.py.")

API_MIN_CONNECTIONS = getattr(settings, 'BILLING_API_MIN_CONNECTIONS', 10)

ENDPOINT_DESCRIPTION_STRING = getattr(
    settings, 'BILLING_ENDPOINT_DESCRIPTION_STRING',
    "tcp:9090:interface=127.0.0.1")

MONTHLY_STATEMENT_TITLE = getattr(
    settings, 'BILLING_MONTHLY_STATEMENT_TITLE', "Monthly Statement")

STATEMENTS_PER_PAGE = getattr(
    settings, 'BILLING_STATEMENTS_PER_PAGE', 12)

STATEMENTS_DEFAULT_ORDER_BY = getattr(
    settings, 'BILLING_STATEMENTS_DEFAULT_ORDER_BY', '-from_date')


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
