from decimal import Decimal

from django import template
from django.utils.translation import ungettext

from go.base.utils import format_currency
from go.billing import settings

register = template.Library()


@register.filter
def format_cents(v):
    """Returns a formatted string representation of a number in dollars from a
    decimal cents value (cents are the billing system's internal representation
    for monetary amounts).
    """
    v = v / Decimal('100.0')
    return format_currency(v, places=settings.DOLLAR_DECIMAL_PLACES)


@register.filter
def format_unit_cost_cents(v):
    """A version of ``format_cents`` tailored to format small fractions of cents
    for displaying unit costs.
    """
    v = v / Decimal('100.0')
    return format_currency(v, places=settings.UNIT_COST_DOLLAR_DECIMAL_PLACES)


@register.filter
def format_credits(v):
    """Returns a formatted string representation of a number in credits from a
    decimal credits value.
    """
    return format_currency(v)


@register.simple_tag
def credit_balance(user):
    """Return the credit balance for the given ``user``'s account.

    If the user has multiple accounts, the first one's balance is returned.
    """
    account = user.account_set.get()
    credits = account.credit_balance

    return "%s %s" % (
        format_credits(credits),
        ungettext("credit", "credits", credits))
