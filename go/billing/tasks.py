from datetime import date

from dateutil.relativedelta import relativedelta

from celery.task import task

from django.db.models import Sum

from go.billing import settings
from go.billing.models import Account, Transaction, Statement, LineItem


@task(ignore_result=True)
def generate_monthly_account_statements():
    today = date.today()
    last_month = today - relativedelta(months=1)
    from_date = date(last_month.year, last_month.month, 1)
    to_date = date(today.year, today.month, 1) - relativedelta(days=1)
    account_list = Account.objects.exclude(
        statement__from_date=from_date,
        statement__to_date=to_date)

    for account in account_list:
        transaction_list = Transaction.objects\
            .filter(account_number=account.account_number,
                    created__gte=from_date,
                    created__lt=(to_date + relativedelta(days=1)))\
            .values('tag_pool_name', 'tag_name', 'message_direction')\
            .annotate(total_cost=Sum('credit_amount'))

        statement = Statement(
            account=account,
            title=settings.MONTHLY_STATEMENT_TITLE,
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
