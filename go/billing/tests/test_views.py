""" Tests for PDF billing statement generation """

from django.core.urlresolvers import reverse

from go.base.tests.helpers import DjangoVumiApiHelper, GoDjangoTestCase
from go.billing.models import Account

from .helpers import mk_statement, mk_transaction


class TestStatementView(GoDjangoTestCase):
    def setUp(self):
        self.vumi_helper = self.add_helper(DjangoVumiApiHelper())
        self.user_helper = self.vumi_helper.make_django_user(superuser=False)
        self.account = Account.objects.get(
            user=self.user_helper.get_django_user())

    def test_statement_accessable(self):
        mk_transaction(self.account)
        statement = mk_statement(self.account)
        client = self.vumi_helper.get_client()
        client.login()
        response = client.get(
            reverse('pdf_statement', kwargs={'statement_id': statement.id}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
