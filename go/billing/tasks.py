from datetime import date

from dateutil.relativedelta import relativedelta

from twisted.python import log
from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks

from celery.task import task

from django.conf import settings

from go.vumitools.billing_worker import BillingApi

from go.billing.models import Account, LineItem


@inlineCallbacks
def _generate_monthly_account_statements():
    try:
        billing_api = BillingApi(settings.GO_BILLING_API_URL)
        today = date.today()
        last_month = today - relativedelta(months=1)
        account_list = Account.objects.all()
        for account in account_list:
            monthly_statement, created = account.monthly_statements\
                .get_or_create(year=last_month.year, month=last_month.month)

            if created:
                result = yield billing_api.get_account_statement(
                    account.account_number, last_month.year, last_month.month)

                line_item_list = []
                for obj in result:
                    line_item_list.append(LineItem(
                        statement=monthly_statement,
                        tag_pool_name=obj.get('tag_pool_name', ''),
                        tag_name=obj.get('tag_name', ''),
                        message_direction=obj.get('message_direction', ''),
                        total_cost=obj.get('total_cost', 0)))
                monthly_statement.line_items.bulk_create(line_item_list)

    except Exception as error:
        log.err(error)
    finally:
        reactor.stop()


@task(ignore_result=True)
def generate_monthly_account_statements(interval):
    reactor.callWhenRunning(_generate_monthly_account_statements)
    reactor.run()
