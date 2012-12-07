from django.test.client import Client
from django.core.urlresolvers import reverse
from django.contrib.auth.models import User

from go.apps.tests.base import DjangoGoApplicationTestCase


class AccountTestCase(DjangoGoApplicationTestCase):

    def setUp(self):
        super(AccountTestCase, self).setUp()
        self.setup_riak_fixtures()
        self.client = Client()
        self.client.login(username='username', password='password')

    def tearDown(self):
        pass

    def test_password_check(self):
        response = self.client.post(reverse('account:index'), {
            'name': 'foo',
            'surname': 'bar',
            'email_address': 'user@domain.com',
            'existing_password': 'wrong',
            '_account': True,
            })
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response, 'account_form', 'existing_password',
            'Invalid password provided')
        # reload from db
        user = User.objects.get(pk=self.user.pk)
        self.assertNotEqual(user.first_name, 'foo')
        self.assertNotEqual(user.last_name, 'bar')
        self.assertEqual(user.email, 'user@domain.com')
        self.assertTrue(user.check_password('password'))

    def test_update_details(self):
        response = self.client.post(reverse('account:index'), {
            'name': 'foo',
            'surname': 'bar',
            'email_address': 'foo@bar.com',
            'existing_password': 'password',
            '_account': True,
            })
        self.assertRedirects(response, reverse('account:index'))
        # reload from db
        user = User.objects.get(pk=self.user.pk)
        self.assertEqual(user.first_name, 'foo')
        self.assertEqual(user.last_name, 'bar')
        self.assertEqual(user.email, 'foo@bar.com')
        self.assertTrue(user.check_password('password'))

    def test_update_password(self):
        response = self.client.post(reverse('account:index'), {
            'name': 'foo',
            'surname': 'bar',
            'email_address': 'user@domain.com',
            'existing_password': 'password',
            'new_password': 'new_password',
            '_account': True,
            })
        self.assertRedirects(response, reverse('account:index'))
        # reload from db
        user = User.objects.get(pk=self.user.pk)
        self.assertTrue(user.check_password('new_password'))
