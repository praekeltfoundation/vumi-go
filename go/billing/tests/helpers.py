""" Helpers for billing tests. """

from datetime import date
from dateutil.relativedelta import relativedelta
from decimal import Decimal

from go.billing import tasks
from go.billing.models import MessageCost, Transaction


def this_month():
    today = date.today()
    next_month = today + relativedelta(months=1)
    from_date = date(today.year, today.month, 1)
    to_date = date(next_month.year, next_month.month, 1)
    to_date = to_date - relativedelta(days=1)
    return [from_date, to_date]


def mk_transaction(account, tag_pool_name='pool1',
                   tag_name="tag1",
                   message_direction=MessageCost.DIRECTION_INBOUND,
                   message_cost=100, markup_percent=10.0,
                   credit_factor=0.25, credit_amount=28,
                   status=Transaction.STATUS_COMPLETED, **kwargs):
    transaction = Transaction(
        account_number=account.account_number,
        tag_pool_name=tag_pool_name,
        tag_name=tag_name,
        message_direction=message_direction,
        message_cost=message_cost,
        markup_percent=Decimal(str(markup_percent)),
        credit_factor=Decimal(str(credit_factor)),
        credit_amount=credit_amount,
        status=status, **kwargs)

    transaction.save()
    return transaction


def mk_statement(account):
    return tasks.generate_monthly_statement(account.id, *this_month())


def get_message_credits(cost, markup):
    return MessageCost.calculate_message_credit_cost(
        Decimal(str(cost)),
        Decimal(str(markup)))


def get_session_credits(cost, markup):
    return MessageCost.calculate_session_credit_cost(
        Decimal(str(cost)),
        Decimal(str(markup)))
