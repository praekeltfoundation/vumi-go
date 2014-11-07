from datetime import date

from dateutil.relativedelta import relativedelta

from celery.task import task, group

from django.db.models import Sum
from django.core import serializers

from go.billing import settings
from go.billing.models import (
    Account, Transaction, Statement, LineItem, TransactionArchive)


def month_range(months_ago=1, today=None):
    """ Return the dates at the start and end of a calendar month.

    :param in months_ago:
        How many months back the range should be.
    :param date today:
        The date which months_ago is relative to.

    :returns:
        A tuple consisting of (from_date, to_date).
    """
    if today is None:
        today = date.today()
    last_month = today - relativedelta(months=months_ago)
    from_date = date(last_month.year, last_month.month, 1)
    to_date = date(today.year, today.month, 1) - relativedelta(days=1)
    return from_date, to_date


@task()
def generate_monthly_statement(account_id, from_date, to_date):
    """Generate a new *Monthly* ``Statement`` for the given ``account_id``
       between the given ``from_date`` and ``to_date``.
    """
    account = Account.objects.get(id=account_id)
    transaction_list = Transaction.objects\
        .filter(account_number=account.account_number,
                created__gte=from_date,
                created__lt=(to_date + relativedelta(days=1)))\
        .values('tag_pool_name', 'tag_name', 'message_direction')\
        .annotate(total_cost=Sum('credit_amount'))

    statement = Statement(
        account=account,
        title=settings.MONTHLY_STATEMENT_TITLE,
        type=Statement.TYPE_MONTHLY,
        from_date=from_date,
        to_date=to_date)

    statement.save()

    line_item_list = []
    for transaction in transaction_list:
        line_item_list.append(LineItem(
            statement=statement,
            tag_pool_name=transaction.get('tag_pool_name', ''),
            tag_name=transaction.get('tag_name', ''),
            message_direction=transaction.get('message_direction', ''),
            total_cost=transaction.get('total_cost', 0)))

    statement.lineitem_set.bulk_create(line_item_list)
    return statement


@task()
def generate_monthly_account_statements():
    """Spawn sub-tasks to generate a *Monthly* ``Statement`` for accounts
       without a *Monthly* statement.
    """
    from_date, to_date = month_range(months_ago=1)
    account_list = Account.objects.exclude(
        statement__type=Statement.TYPE_MONTHLY,
        statement__from_date=from_date,
        statement__to_date=to_date)

    task_list = []
    for account in account_list:
        task_list.append(
            generate_monthly_statement.s(account.id, from_date, to_date))

    return group(task_list)()


@task
def archive_monthly_transactions(months_ago=3):
    """Spawn sub-tasks to archive transactions from N months ago."""
    from_date, to_date = month_range(months_ago=months_ago)
    account_list = Account.objects.exclude(
        transactionarchive__from_date=from_date,
        transactionarchive__to_date=to_date)

    task_list = []
    for account in account_list:
        task_list.append(archive_transactions.s(
            account.id, from_date, to_date))

    return group(task_list)()


@task()
def archive_transactions(account_id, from_date, to_date, serializer='json'):
    account = Account.objects.get(id=account_id)
    formatter = serializers.get(serializer)()
    filename = (
        u"transactions-%(account_number)s-%(from)s-to-%(to)s"
        ".%(serializer)s" % {
            "account_number": account.account_number,
            "from": from_date,
            "to": to_date,
            "serializer": serializer,
        })

    archive = TransactionArchive.create(
        account=account, filename=filename,
        from_date=from_date, to_date=to_date,
        status=TransactionArchive.PENDING)

    transaction_list = Transaction.objects.filter(
        account_number=account.account_number,
        created__gte=from_date,
        created__lt=(to_date + relativedelta(days=1)))

    for transaction in transaction_list:
        formatter.serialize([transaction])
        # TODO: write to S3

    archive.status = TransactionArchive.COMPLETED
    archive.save()
