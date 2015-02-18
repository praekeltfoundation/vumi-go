""" Test for billing admin. """

from django.core.urlresolvers import reverse

from go.base.tests.helpers import GoDjangoTestCase, DjangoVumiApiHelper
from go.billing.models import Account

from .helpers import mk_statement, mk_transaction


class TestStatementAdmin(GoDjangoTestCase):
    def setUp(self):
        self.vumi_helper = self.add_helper(DjangoVumiApiHelper())
        self.user_helper = self.vumi_helper.make_django_user(superuser=True)

        self.vumi_helper.setup_tagpool(u'pool1', ['tag1'])
        self.user_helper.add_tagpool_permission(u'pool1')

        self.account = Account.objects.get(
            user=self.user_helper.get_django_user())

    def test_admin_accessible(self):
        client = self.vumi_helper.get_client()
        client.login()
        response = client.get(
            reverse('admin:app_list', kwargs={'app_label': 'billing'}))
        self.assertContains(response, "Billing administration")
        self.assertContains(response, "Accounts")
        self.assertContains(response, "Message costs")
        self.assertContains(response, "Statements")
        self.assertContains(response, "Tag pools")
        self.assertContains(response, "Transactions")
        self.assertContains(response, "Low credit notifications")
        self.assertContains(response, "Transaction archives")

    def test_link_to_html_view(self):
        statement = mk_statement(self.account)
        client = self.vumi_helper.get_client()
        client.login()
        response = client.get(reverse('admin:billing_statement_changelist'))
        self.assertContains(response, "1 total")
        self.assertContains(
            response,
            '<a href="/billing/statement/%s">' % (statement.id,))

    def test_statement_admin_view(self):
        mk_transaction(self.account)
        statement = mk_statement(self.account)
        client = self.vumi_helper.get_client()
        client.login()
        response = client.get(
            reverse('admin:billing_statement_change', args=[statement.id]))
        self.assertContains(response, "Monthly Statement for")
        self.assertContains(response, "Account")
        # check that line items have been inlined
        self.assertContains(response, "Channel")
        self.assertContains(response, "Channel type")
        self.assertContains(response, "Description")
        self.assertContains(response, "Units")
        self.assertContains(response, "Credits")
        self.assertContains(response, "Unit cost")
        self.assertContains(response, "Cost")

    def test_account_admin_view(self):
        client = self.vumi_helper.get_client()
        client.login()
        response = client.get(
            reverse('admin:billing_account_changelist'))
        self.assertContains(response, 'Select account to change')
        self.assertContains(response, 'Account number')
        self.assertContains(response, 'User')
        self.assertContains(response, 'Description')
        self.assertContains(response, 'Credit balance')
        self.assertContains(response, 'Last topup balance')
        self.assertContains(response, 'Is developer')
