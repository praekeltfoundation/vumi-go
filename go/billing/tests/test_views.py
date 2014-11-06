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

    def mk_statement(self, transactions=2):
        for _i in range(transactions):
            mk_transaction(self.account)
        return mk_statement(self.account)

    def assert_is_pdf(self, response):
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertTrue(response.content.startswith('%PDF-'))

    def get_statement_pdf(self, username, statement):
        client = self.vumi_helper.get_client(username=username)
        return client.get(
            reverse('pdf_statement', kwargs={'statement_id': statement.id}))

    def check_statement_accessible_by(self, username, statement):
        response = self.get_statement_pdf(username, statement)
        self.assert_is_pdf(response)

    def check_statement_not_accessible_by(self, username, statement):
        response = self.get_statement_pdf(username, statement)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response['Content-Type'].split(';')[0], 'text/html')

    def test_statement_accessable_by_owner(self):
        statement = statement = self.mk_statement()
        self.check_statement_accessible_by(
            self.user_helper.get_django_user(), statement)

    def test_statement_accessable_by_superuser(self):
        statement = self.mk_statement()
        self.vumi_helper.make_django_user(
            email='super@example.com', superuser=True)
        self.check_statement_accessible_by('super@example.com', statement)

    def test_statement_accessable_by_staff(self):
        statement = self.mk_statement()
        user_helper = self.vumi_helper.make_django_user(
            email='staff@example.com')
        user = user_helper.get_django_user()
        user.is_staff = True
        user.save()
        self.check_statement_accessible_by('staff@example.com', statement)

    def test_statement_hidden_when_not_accessible(self):
        statement = self.mk_statement()
        self.vumi_helper.make_django_user(
            email='other.user@example.com')
        self.check_statement_not_accessible_by(
            'other.user@example.com', statement)
