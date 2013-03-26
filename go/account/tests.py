import urlparse

from django.test.client import Client
from django.core.urlresolvers import reverse
from django.contrib.auth.models import User
from django.core import mail
from django.conf import settings


from go.apps.tests.base import DjangoGoApplicationTestCase
from go.account.utils import send_user_account_summary
from go.account.tasks import send_scheduled_account_summary


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

    def confirm(self, token_url):
        url = urlparse.urlsplit(token_url)
        return self.client.get(url.path, follow=True)

    def test_update_details(self):
        response = self.client.post(reverse('account:index'), {
            'name': 'foo',
            'surname': 'bar',
            'email_address': 'foo@bar.com',
            'existing_password': 'password',
            '_account': True,
            })
        self.assertRedirects(response, reverse('account:index'))
        token_url = response.context['token_url']
        self.confirm(token_url)
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
        token_url = response.context['token_url']
        self.confirm(token_url)
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
            token_url = response.context['token_url']
            self.confirm(token_url)
            profile = User.objects.get(pk=self.user.pk).get_profile()
            user_account = profile.get_user_account()
            self.assertEqual(user_account.msisdn, '+27761234567')

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
            self.assertEqual([], mail.outbox)
            profile = User.objects.get(pk=self.user.pk).get_profile()
            user_account = profile.get_user_account()
            self.assertEqual(user_account.msisdn, None)

    def test_confirm_start_conversation(self):
        response = self.client.post(reverse('account:index'), {
            'name': 'foo',
            'surname': 'bar',
            'email_address': 'user@domain.com',
            'existing_password': 'password',
            'msisdn': '+27761234567',
            'confirm_start_conversation': True,
            '_account': True,
            })
        token_url = response.context['token_url']
        response = self.client.get(reverse('account:index'))
        self.assertContains(response,
            'Please confirm this change by clicking on the link that was '
            'just sent to your mailbox.')
        profile = User.objects.get(pk=self.user.pk).get_profile()
        user_account = profile.get_user_account()
        self.assertFalse(user_account.confirm_start_conversation)

        [email] = mail.outbox
        self.assertTrue(token_url in email.body)

        response = self.confirm(token_url)
        self.assertContains(response, 'Your details are being updated')

        profile = User.objects.get(pk=self.user.pk).get_profile()
        user_account = profile.get_user_account()
        self.assertTrue(user_account.confirm_start_conversation)

    def test_email_summary(self):
        user_account = self.user.get_profile().get_user_account()
        response = self.client.post(reverse('account:index'), {
            'name': 'foo',
            'surname': 'bar',
            'email_address': 'user@domain.com',
            'existing_password': 'password',
            'msisdn': '+27761234567',
            'email_summary': 'daily',
            '_account': True,
            })
        token_url = response.context['token_url']

        self.assertNotEqual(user_account.email_summary, 'daily')

        response = self.confirm(token_url)
        self.assertContains(response, 'Your details are being updated')

        user_account = self.user.get_profile().get_user_account()
        self.assertEqual(user_account.email_summary, 'daily')

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
        self.assertEqual([], mail.outbox)


class EmailTestCase(DjangoGoApplicationTestCase):

    def setUp(self):
        super(EmailTestCase, self).setUp()
        self.setup_riak_fixtures()
        self.client = Client()
        self.client.login(username='username', password='password')
        self.declare_longcode_tags()

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

    def test_daily_account_summary(self):
        contact_store = self.user_api.contact_store
        contact_keys = contact_store.list_contacts()
        [contacts] = contact_store.contacts.load_all_bunches(contact_keys)
        for contact in contacts:
            # create a duplicate
            contact_store.new_contact(msisdn=contact.msisdn)

        self.put_sample_messages_in_conversation(self.user_api,
                                                    self.conv_key, 10)
        # create a second conversation to test sorting
        self.mkconversation()

        # schedule the task
        send_user_account_summary(self.user)

        [email] = mail.outbox
        print email.body
        self.assertEqual(email.subject, 'Vumi Go Account Summary')
        self.assertEqual(email.from_email, settings.DEFAULT_FROM_EMAIL)
        self.assertEqual(email.recipients(), [self.user.email])
        self.assertTrue('number of contacts: 2' in email.body)
        self.assertTrue('number of unique contacts by contact number: 1'
                            in email.body)
        self.assertTrue('number of messages sent: 10' in email.body)
        self.assertTrue('number of messages received: 10' in email.body)
        self.assertTrue('Send Bulk SMS and track replies' in email.body)
        self.assertTrue('Test Conversation' in email.body)
        self.assertTrue('Sent: 10 to 10 uniques.' in email.body)
        self.assertTrue('Received: 10 from 10 uniques.' in email.body)
        self.assertTrue('"Send Bulk SMS and track replies" Sent: 10'
                            in email.body)
        self.assertTrue('"Send Bulk SMS and track replies" Received: 10'
                            in email.body)

    def test_send_scheduled_account_summary_task(self):
        profile = self.user.get_profile()
        user_account = profile.get_user_account()
        user_account.email_summary = u'daily'
        user_account.save()

        send_scheduled_account_summary('daily')
        send_scheduled_account_summary('weekly')

        [daily] = mail.outbox
        self.assertEqual(daily.subject, 'Vumi Go Account Summary')

        user_account.email_summary = u'weekly'
        user_account.save()

        send_scheduled_account_summary('daily')
        send_scheduled_account_summary('weekly')

        [daily, weekly] = mail.outbox
        self.assertEqual(weekly.subject, 'Vumi Go Account Summary')
