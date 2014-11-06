""" Test for billing admin. """

from django.core.urlresolvers import reverse

from go.base.tests.helpers import GoDjangoTestCase, DjangoVumiApiHelper
from go.billing.models import Account

from .helpers import mk_statement, mk_transaction


class TestStatementAdmin(GoDjangoTestCase):
    def setUp(self):
        self.vumi_helper = self.add_helper(DjangoVumiApiHelper())
        self.user_helper = self.vumi_helper.make_django_user(superuser=True)
        self.account = Account.objects.get(
            user=self.user_helper.get_django_user())

    def test_admin_accessible(self):
        client = self.vumi_helper.get_client()
        client.login()
        response = client.get(
            reverse('admin:app_list', kwargs={'app_label': 'billing'}))
        self.assertContains(response, "Models in the Billing application")
        self.assertContains(response, "Accounts")
        self.assertContains(response, "Message costs")
        self.assertContains(response, "Statements")
        self.assertContains(response, "Tag pools")
        self.assertContains(response, "Transactions")

    def test_link_to_pdf_view(self):
        statement = mk_statement(self.account)
        client = self.vumi_helper.get_client()
        client.login()
        response = client.get(reverse('admin:billing_statement_changelist'))
        self.assertContains(response, "1 statement")
        self.assertContains(
            response, '<a href="/billing/statement/%s">pdf</a>' % statement.id)

    def test_statement_admin_view(self):
        mk_transaction(self.account)
        statement = mk_statement(self.account)
        client = self.vumi_helper.get_client()
        client.login()
        response = client.get(
            reverse('admin:billing_statement_change', args=[statement.id]))
        self.assertContains(response, "Monthly Statement for")
        self.assertContains(response, "Account:")
        # check that line items have been inlined
        self.assertContains(response, "Tag pool name")
        self.assertContains(response, "Tag name")
        self.assertContains(response, "Message direction")
        self.assertContains(response, "Monthly Statement line item")
