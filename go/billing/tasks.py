from datetime import date

from dateutil.relativedelta import relativedelta

from celery.task import task, group

from django.db.models import Sum, Count
from django.conf import settings as go_settings

from go.billing import settings
from go.billing.models import (
    Account, Transaction, MessageCost, Statement, LineItem)
from go.vumitools.api import VumiUserApi


def get_message_transactions(account, from_date, to_date):
    transactions = Transaction.objects.filter(
        account_number=account.account_number,
        created__gte=from_date,
        created__lt=(to_date + relativedelta(days=1)))

    transactions = transactions.values(
        'tag_pool_name',
        'tag_name',
        'message_direction',
        'message_cost',
        'markup_percent')

    transactions = transactions.annotate(
        count=Count('id'), total_message_cost=Sum('message_cost'))

    return transactions


def get_session_transactions(account, from_date, to_date):
    transactions = Transaction.objects.filter(
        account_number=account.account_number,
        created__gte=from_date,
        created__lt=(to_date + relativedelta(days=1)))

    transactions = transactions.filter(session_created=True)

    transactions = transactions.values(
        'tag_pool_name',
        'tag_name',
        'session_cost',
        'markup_percent')

    transactions = transactions.annotate(
        count=Count('id'), total_session_cost=Sum('session_cost'))

    return transactions


def get_tagpools(account):
    config = go_settings.VUMI_API_CONFIG
    user_api = VumiUserApi.from_config_sync(account.account_number, config)
    return user_api.tagpools()


def get_provider_name(transaction, tagpools):
    return tagpools.display_name(transaction['tag_pool_name'])


def get_channel_name(transaction, tagpools):
    return transaction['tag_name']


def get_message_cost(transaction):
    return transaction['total_message_cost']


def get_session_cost(transaction):
    return transaction['total_session_cost']


def get_count(transaction):
    return transaction['count']


def get_message_unit_cost(transaction):
    count = get_count(transaction)
    return get_message_cost(transaction) / count if count != 0 else count


def get_session_unit_cost(transaction):
    count = get_count(transaction)
    return get_session_cost(transaction) / count if count != 0 else count


def get_message_credits(transaction):
    cost = get_message_cost(transaction)
    markup = transaction['markup_percent']
    return MessageCost.calculate_message_credit_cost(cost, markup)


def get_session_credits(transaction):
    cost = get_session_cost(transaction)
    markup = transaction['markup_percent']
    return MessageCost.calculate_session_credit_cost(cost, markup)


def get_channel_type(transaction, tagpools):
    delivery_class = tagpools.delivery_class(transaction['tag_pool_name'])
    return tagpools.delivery_class_name(delivery_class)


def get_message_description(transaction):
    if transaction['message_direction'] == MessageCost.DIRECTION_INBOUND:
        return 'Messages received'
    else:
        return 'Messages sent'


def make_message_item(statement, transaction, tagpools):
    return LineItem(
        units=get_count(transaction),
        statement=statement,
        cost=get_message_cost(transaction),
        credits=get_message_credits(transaction),
        channel=get_channel_name(transaction, tagpools),
        billed_by=get_provider_name(transaction, tagpools),
        unit_cost=get_message_unit_cost(transaction),
        channel_type=get_channel_type(transaction, tagpools),
        description=get_message_description(transaction))


def make_session_item(statement, transaction, tagpools):
    return LineItem(
        units=get_count(transaction),
        statement=statement,
        cost=get_session_cost(transaction),
        credits=get_session_credits(transaction),
        channel=get_channel_name(transaction, tagpools),
        billed_by=get_provider_name(transaction, tagpools),
        unit_cost=get_session_unit_cost(transaction),
        channel_type=get_channel_type(transaction, tagpools),
        description='Sessions')


def make_message_items(account, statement, tagpools, from_date, to_date):
    transactions = get_message_transactions(account, from_date, to_date)

    return [
        make_message_item(statement, transaction, tagpools)
        for transaction in transactions]


def make_session_items(account, statement, tagpools, from_date, to_date):
    transactions = get_session_transactions(account, from_date, to_date)

    return [
        make_session_item(statement, transaction, tagpools)
        for transaction in transactions]


@task()
def generate_monthly_statement(account_id, from_date, to_date):
    """Generate a new *Monthly* ``Statement`` for the given ``account``
       between the given ``from_date`` and ``to_date``.
    """
    account = Account.objects.get(id=account_id)
    tagpools = get_tagpools(account)

    statement = Statement(
        account=account,
        title=settings.MONTHLY_STATEMENT_TITLE,
        type=Statement.TYPE_MONTHLY,
        from_date=from_date,
        to_date=to_date)

    statement.save()

    items = []
    items.extend(make_message_items(
        account, statement, tagpools, from_date, to_date))
    items.extend(make_session_items(
        account, statement, tagpools, from_date, to_date))

    statement.lineitem_set.bulk_create(items)
    return statement


@task()
def generate_monthly_account_statements():
    """Spawn sub-tasks to generate a *Monthly* ``Statement`` for accounts
       without a *Monthly* statement.
    """
    today = date.today()
    last_month = today - relativedelta(months=1)
    from_date = date(last_month.year, last_month.month, 1)
    to_date = date(today.year, today.month, 1) - relativedelta(days=1)
    account_list = Account.objects.exclude(
        statement__type=Statement.TYPE_MONTHLY,
        statement__from_date=from_date,
        statement__to_date=to_date)

    task_list = []
    for account in account_list:
        task_list.append(
            generate_monthly_statement.s(account.id, from_date, to_date))

    return group(task_list)()
