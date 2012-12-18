from django.test.client import Client
from django.core.urlresolvers import reverse
from django.contrib.auth.models import User
from django.core import mail

from go.apps.tests.base import DjangoGoApplicationTestCase


class AccountTestCase(DjangoGoApplicationTestCase):

    def setUp(self):
        super(AccountTestCase, self).setUp()
        self.setup_riak_fixtures()
        self.client = Client()
        self.client.login(username='username', password='password')

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

    def test_update_msisdn_valid(self):
        valid = ['+27761234567', '27761234567']
        for msisdn in valid:
            response = self.client.post(reverse('account:index'), {
                'name': 'foo',
                'surname': 'bar',
                'email_address': 'user@domain.com',
                'msisdn': msisdn,
                'existing_password': 'password',
                '_account': True,
                })
            self.assertRedirects(response, reverse('account:index'))
            profile = User.objects.get(pk=self.user.pk).get_profile()
            self.assertEqual(profile.msisdn, '+27761234567')

    def test_update_msisdn_invalid(self):
        invalid = ['+123', '123', 'abc']
        for msisdn in invalid:
            response = self.client.post(reverse('account:index'), {
                'name': 'foo',
                'surname': 'bar',
                'email_address': 'user@domain.com',
                'msisdn': msisdn,
                'existing_password': 'password',
                '_account': True,
                })
            self.assertFormError(response, 'account_form', 'msisdn',
                'Please provide a valid phone number.')
            profile = User.objects.get(pk=self.user.pk).get_profile()
            self.assertEqual(profile.msisdn, None)

    def test_confirm_start_conversation(self):
        self.client.post(reverse('account:index'), {
            'name': 'foo',
            'surname': 'bar',
            'email_address': 'user@domain.com',
            'existing_password': 'password',
            '_account': True,
            })
        profile = User.objects.get(pk=self.user.pk).get_profile()
        self.assertFalse(profile.confirm_start_conversation)

        self.client.post(reverse('account:index'), {
            'name': 'foo',
            'surname': 'bar',
            'email_address': 'user@domain.com',
            'existing_password': 'password',
            'confirm_start_conversation': False,
            '_account': True,
            })
        profile = User.objects.get(pk=self.user.pk).get_profile()
        self.assertFalse(profile.confirm_start_conversation)

        self.client.post(reverse('account:index'), {
            'name': 'foo',
            'surname': 'bar',
            'email_address': 'user@domain.com',
            'existing_password': 'password',
            'msisdn': '+27761234567',
            'confirm_start_conversation': True,
            '_account': True,
            })
        profile = User.objects.get(pk=self.user.pk).get_profile()
        self.assertTrue(profile.confirm_start_conversation)

    def test_require_msisdn_if_confirm_start_conversation(self):
        response = self.client.post(reverse('account:index'), {
            'name': 'foo',
            'surname': 'bar',
            'email_address': 'user@domain.com',
            'confirm_start_conversation': True,
            'existing_password': 'password',
            '_account': True,
            })
        self.assertFormError(response, 'account_form', 'msisdn',
            'Please provide a valid phone number.')


class EmailTestCase(DjangoGoApplicationTestCase):

    def setUp(self):
        super(EmailTestCase, self).setUp()
        self.setup_riak_fixtures()
        self.client = Client()
        self.client.login(username='username', password='password')

    def test_email_sending(self):
        response = self.client.post(reverse('account:index'), {
            '_email': True,
            'subject': 'foo',
            'message': 'bar',
            })
        self.assertRedirects(response, reverse('account:index'))
        [email] = mail.outbox
        self.assertEqual(email.subject, 'foo')
        self.assertEqual(email.from_email, self.user.email)
        self.assertTrue('bar' in email.body)
