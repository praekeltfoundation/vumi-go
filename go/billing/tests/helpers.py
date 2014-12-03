""" Helpers for billing tests. """

from datetime import date
from dateutil.relativedelta import relativedelta
from decimal import Decimal

from go.billing import settings
from go.billing.models import MessageCost, Transaction, Statement, LineItem


def start_of_month(day):
    return date(day.year, day.month, 1)


def end_of_month(day):
    next_month = day + relativedelta(months=1)
    result = date(next_month.year, next_month.month, 1)
    result = result - relativedelta(days=1)
    return result


def this_month(day=None):
    if day is None:
        day = date.today()
    return [start_of_month(day), end_of_month(day)]


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


def mk_statement(account,
                 title=settings.MONTHLY_STATEMENT_TITLE,
                 type=Statement.TYPE_MONTHLY,
                 from_date=None,
                 to_date=None,
                 items=()):
    if from_date is None:
        from_date = start_of_month()

    if to_date is None:
        to_date = end_of_month()

    statement = Statement(
        account=account,
        title=settings.MONTHLY_STATEMENT_TITLE,
        type=Statement.TYPE_MONTHLY,
        from_date=from_date,
        to_date=to_date)

    statement.save()

    statement.lineitem_set.bulk_create((
        LineItem(statement=statement, **item) for item in items))

    return statement


def get_message_credits(cost, markup):
    return MessageCost.calculate_message_credit_cost(
        Decimal(str(cost)),
        Decimal(str(markup)))


def get_session_credits(cost, markup):
    return MessageCost.calculate_session_credit_cost(
        Decimal(str(cost)),
        Decimal(str(markup)))


def get_line_items(statement):
    items = statement.lineitem_set.all()
    return items.order_by('description', 'credits')
