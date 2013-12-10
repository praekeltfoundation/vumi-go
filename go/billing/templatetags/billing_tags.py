from django import template
from django.utils.translation import ungettext

register = template.Library()


@register.simple_tag
def credit_balance(user):
    """Return the credit balance for the given ``user``'s account.

    If the user has multiple accounts, the first one's balance is returned.
    """
    try:
        account = user.account_set.all()[0]
        credit_balance = account.credit_balance
    except IndexError:
        credit_balance = 0

    return ungettext(
        "%(credit_balance)d credit",
        "%(credit_balance)d credits",
        credit_balance) % {'credit_balance': credit_balance}
