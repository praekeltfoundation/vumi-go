""" Tests for PDF billing statement generation """

from datetime import date
from dateutil.relativedelta import relativedelta
from decimal import Decimal

from django.core.urlresolvers import reverse
from go.base.tests.helpers import DjangoVumiApiHelper, GoDjangoTestCase
from go.billing import tasks
from go.billing.models import Account, MessageCost, Transaction


class TestStatementView(GoDjangoTestCase):
    def setUp(self):
        self.vumi_helper = self.add_helper(DjangoVumiApiHelper())
        self.user_helper = self.vumi_helper.make_django_user(superuser=False)
        self.account = Account.objects.get(
            user=self.user_helper.get_django_user())

    def _mk_transaction(self, account_number, tag_pool_name='pool1',
                        tag_name="tag1",
                        message_direction=MessageCost.DIRECTION_INBOUND,
                        message_cost=100, markup_percent=10.0,
                        credit_factor=0.25, credit_amount=28,
                        status=Transaction.STATUS_COMPLETED, **kwargs):
        transaction = Transaction(
            account_number=account_number,
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

    def _mk_statement(self):
        today = date.today()
        next_month = today + relativedelta(months=1)
        from_date = date(today.year, today.month, 1)
        to_date = (date(next_month.year, next_month.month, 1)
                   - relativedelta(days=1))

        return tasks.generate_monthly_statement(
            self.account.id, from_date, to_date)

    def test_statement_accessable(self):
        self._mk_transaction(self.account.account_number)
        statement = self._mk_statement()
        client = self.vumi_helper.get_client()
        client.login()
        response = client.get(
            reverse('pdf_statement', kwargs={'statement_id': statement.id}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
