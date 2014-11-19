from datetime import date

from dateutil.relativedelta import relativedelta

from celery.task import task, group

from django.db.models import Sum
from django.conf import settings as go_settings

from go.billing import settings
from go.billing.models import (
    Account, Transaction, MessageCost, Statement, LineItem)
from go.vumitools.api import VumiUserApi


def get_tagpools(account):
    config = go_settings.VUMI_API_CONFIG
    user_api = VumiUserApi.from_config_sync(account.account_number, config)
    return user_api.tagpools()


def get_message_transactions(account, from_date, to_date):
    transactions = Transaction.objects.filter(
        account_number=account.account_number,
        created__gte=from_date,
        created__lt=(to_date + relativedelta(days=1)))

    transactions = transactions.values(
        'tag_pool_name', 'tag_name', 'message_direction')

    transactions = transactions.annotate(
        cost=Sum('message_cost'), credits=Sum('credit_amount'))

    return transactions


def make_provider_item(statement, transaction, tagpools, count, description,
                       credits, cost):
    pool = transaction['tag_pool_name']
    count = count if count != 0 else 1
    delivery_class = tagpools.delivery_class(pool)
    delivery_class = tagpools.delivery_class_name(delivery_class)

    return LineItem(
        statement=statement,
        billed_by=tagpools.display_name(pool),
        channel=transaction['tag_name'],
        channel_type=delivery_class,
        description=description,
        credits=credits,
        units=count,
        unit_cost=cost / count,
        cost=cost)


def make_message_item(statement, transaction, tagpools, count):
    if transaction['message_direction'] == MessageCost.DIRECTION_INBOUND:
        description = 'Messages received (including sessions)'
    else:
        description = 'Messages sent (including sessions)'

    return make_provider_item(
        statement=statement,
        transaction=transaction,
        tagpools=tagpools,
        count=count,
        description=description,
        credits=transaction['credits'],
        cost=transaction['cost'])


def make_message_items(account, statement, tagpools, from_date, to_date):
    transactions = get_message_transactions(account, from_date, to_date)
    count = len(transactions)
    return [
        make_message_item(statement, transaction, tagpools, count)
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

    line_items = make_message_items(
        account, statement, tagpools, from_date, to_date)

    statement.lineitem_set.bulk_create(line_items)
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
