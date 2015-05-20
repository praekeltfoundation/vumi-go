""" Helpers for billing tests. """

from datetime import date
from dateutil.relativedelta import relativedelta
from decimal import Decimal

from go.billing import settings
from go.billing.models import (
    TagPool, Account, MessageCost, Transaction, Statement, LineItem)


def start_of_month(day=None):
    if day is None:
        day = date.today()
    return date(day.year, day.month, 1)


def end_of_month(day=None):
    if day is None:
        day = date.today()
    next_month = day + relativedelta(months=1)
    result = date(next_month.year, next_month.month, 1)
    result = result - relativedelta(days=1)
    return result


def this_month(day=None):
    if day is None:
        day = date.today()
    return (start_of_month(day), end_of_month(day))


def maybe_decimal(v):
    return Decimal(str(v)) if v is not None else None


def get_billing_account(user_account):
    return Account.objects.get(user=user_account)


def mk_tagpool(name):
    tagpool = TagPool(name=name)
    tagpool.save()
    return tagpool


def mk_message_cost(**fields):
    fields['message_cost'] = maybe_decimal(fields.get('message_cost', 0.0))
    fields['session_cost'] = maybe_decimal(fields.get('session_cost', 0.0))
    fields['storage_cost'] = maybe_decimal(fields.get('storage_cost', 0.0))
    fields['session_unit_cost'] = maybe_decimal(
        fields.get('session_unit_cost', 0.0))
    fields['session_unit_time'] = maybe_decimal(
        fields.get('session_unit_time', 0.0))
    fields['markup_percent'] = maybe_decimal(fields.get('markup_percent', 0.0))
    fields.setdefault('message_direction', MessageCost.DIRECTION_INBOUND)

    cost = MessageCost(**fields)
    cost.save()

    return cost


def mk_transaction(account, tag_pool_name='pool1',
                   tag_name="tag1",
                   transaction_type=Transaction.TRANSACTION_TYPE_MESSAGE,
                   message_direction=MessageCost.DIRECTION_INBOUND,
                   message_cost=100, storage_cost=50, session_cost=10,
                   session_unit_cost=10, session_unit_time=20,
                   session_length_cost=10, session_length=20,
                   markup_percent=10.0, credit_factor=0.25, credit_amount=28,
                   provider=None, status=Transaction.STATUS_COMPLETED,
                   created=None, **kwargs):
    transaction = Transaction(
        account_number=account.account_number,
        transaction_type=transaction_type,
        tag_pool_name=tag_pool_name,
        tag_name=tag_name,
        provider=provider,
        message_direction=message_direction,
        message_cost=maybe_decimal(message_cost),
        storage_cost=maybe_decimal(storage_cost),
        session_cost=maybe_decimal(session_cost),
        session_unit_cost=maybe_decimal(session_unit_cost),
        session_unit_time=maybe_decimal(session_unit_time),
        session_length_cost=maybe_decimal(session_length_cost),
        markup_percent=maybe_decimal(markup_percent),
        credit_factor=maybe_decimal(credit_factor),
        credit_amount=credit_amount,
        message_credits=get_message_credits(message_cost, markup_percent),
        storage_credits=get_storage_credits(storage_cost, markup_percent),
        session_credits=get_session_credits(session_cost, markup_percent),
        session_length_credits=get_session_length_credits(
            session_length_cost, markup_percent),
        session_length=maybe_decimal(session_length),
        status=status, **kwargs)

    transaction.save()

    if created is not None:
        # a double-save is needed here because transaction.create is
        # overridden by auto_add_now when the transaction is first
        # created.
        transaction.created = created
        transaction.save()
    return transaction


def mk_statement(account,
                 title=settings.MONTHLY_STATEMENT_TITLE,
                 statement_type=Statement.TYPE_MONTHLY,
                 from_date=None,
                 to_date=None,
                 items=()):
    if from_date is None:
        from_date = start_of_month()

    if to_date is None:
        to_date = end_of_month()

    statement = Statement(
        account=account,
        title=title,
        type=statement_type,
        from_date=from_date,
        to_date=to_date)

    statement.save()

    statement.lineitem_set.bulk_create((
        LineItem(statement=statement, **item) for item in items))

    return statement


def get_session_length_cost(unit_cost, unit_length, length):
    return MessageCost.calculate_session_length_cost(
        maybe_decimal(unit_cost),
        maybe_decimal(unit_length),
        maybe_decimal(length))


def get_message_credits(cost, markup):
    if cost is None or markup is None:
        return None
    else:
        return MessageCost.calculate_message_credit_cost(
            maybe_decimal(cost),
            maybe_decimal(markup))


def get_session_credits(cost, markup):
    if cost is None or markup is None:
        return None
    else:
        return MessageCost.calculate_session_credit_cost(
            maybe_decimal(cost),
            maybe_decimal(markup))


def get_storage_credits(cost, markup):
    if cost is None or markup is None:
        return None
    else:
        return MessageCost.calculate_storage_credit_cost(
            maybe_decimal(cost),
            maybe_decimal(markup))


def get_session_length_credits(cost, markup):
    if cost is None or markup is None:
        return None
    else:
        return MessageCost.calculate_session_length_credit_cost(
            maybe_decimal(cost), maybe_decimal(markup))


def get_line_items(statement):
    items = statement.lineitem_set.all()
    return items.order_by('description', 'credits')
