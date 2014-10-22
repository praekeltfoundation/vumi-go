""" Test for billing admin. """

from go.base.tests.helpers import GoDjangoTestCase, DjangoVumiApiHelper

from django.core.urlresolvers import reverse


class TestStatementAdmin(GoDjangoTestCase):
    def setUp(self):
        self.vumi_helper = self.add_helper(DjangoVumiApiHelper())
        self.user_helper = self.vumi_helper.make_django_user(superuser=True)

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
