import mock

from datetime import date

from decimal import Decimal

from dateutil.relativedelta import relativedelta

from go.base.tests.utils import VumiGoDjangoTestCase

from go.billing.models import MessageCost, Account, Transaction, Statement
from go.billing import tasks


class TestMonthlyStatementTask(VumiGoDjangoTestCase):

    def setUp(self):
        super(TestMonthlyStatementTask, self).setUp()
        self.setup_user_api()

    def _mk_account(self):
        account = Account(
            user=self.django_user,
            account_number=self.user_api.user_account_key)

        account.save()
        return account

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

    @mock.patch('go.billing.tasks.generate_monthly_statement.s',
                new_callable=mock.MagicMock)
    def test_generate_monthly_statements(self, s):
        account = self._mk_account()
        today = date.today()
        last_month = today - relativedelta(months=1)
        self._mk_transaction(account.account_number, created=last_month,
                             last_modified=last_month)

        self._mk_transaction(
            account.account_number,
            message_direction=MessageCost.DIRECTION_OUTBOUND,
            created=last_month, last_modified=last_month)

        tasks.generate_monthly_account_statements()

        from_date = date(last_month.year, last_month.month, 1)
        to_date = date(today.year, today.month, 1) - relativedelta(days=1)
        s.assert_called_with(account.id, from_date, to_date)

    def test_generate_monthly_statement(self):
        account = self._mk_account()
        self._mk_transaction(account.account_number)
        self._mk_transaction(
            account.account_number,
            message_direction=MessageCost.DIRECTION_OUTBOUND)

        today = date.today()
        next_month = today + relativedelta(months=1)
        from_date = date(today.year, today.month, 1)
        to_date = (date(next_month.year, next_month.month, 1)
                   - relativedelta(days=1))

        result = tasks.generate_monthly_statement(account.id, from_date,
                                                  to_date)

        statement = Statement.objects.get(account=account,
                                          type=Statement.TYPE_MONTHLY)

        self.assertEqual(result, statement)
        self.assertEqual(statement.lineitem_set.count(), 2)
