import urlparse

from django.core.urlresolvers import reverse
from django.contrib.auth.models import User
from django.core import mail
from django.conf import settings
from django.utils.unittest import skip

from go.account.utils import send_user_account_summary
from go.account.tasks import send_scheduled_account_summary
from go.base.tests.utils import VumiGoDjangoTestCase


class AccountTestCase(VumiGoDjangoTestCase):
    use_riak = True

    def setUp(self):
        super(AccountTestCase, self).setUp()
        self.setup_api()
        self.setup_user_api()
        self.setup_client()

    def confirm(self, token_url):
        url = urlparse.urlsplit(token_url)
        return self.client.get(url.path, follow=True)

    def test_update_details(self):
        response = self.client.post(reverse('account:details'), {
            'name': 'foo',
            'surname': 'bar',
            'email_address': 'foo@bar.com',
            'existing_password': 'password',
            '_account': True,
            })

        token_url = response.context['token_url']

        [email] = mail.outbox
        self.assertTrue(token_url in email.body)

        # reload from db
        self.confirm(token_url)
        user = User.objects.get(pk=self.django_user.pk)
        self.assertEqual(user.first_name, 'foo')
        self.assertEqual(user.last_name, 'bar')
        self.assertEqual(user.email, 'foo@bar.com')
        self.assertTrue(user.check_password('password'))

    @skip("This happens in a different place now and the test needs updating.")
    def test_update_password(self):
        response = self.client.post(reverse('account:details'), {
            'name': 'foo',
            'surname': 'bar',
            'email_address': 'user@domain.com',
            'existing_password': 'password',
            'new_password': 'new_password',
            '_account': True,
            })
        token_url = response.context['token_url']
        self.confirm(token_url)
        # reload from db
        user = User.objects.get(pk=self.django_user.pk)
        self.assertTrue(user.check_password('new_password'))

    def test_update_msisdn_valid(self):
        valid = ['+27761234567', '27761234567']
        for msisdn in valid:
            response = self.client.post(reverse('account:details'), {
                'name': 'foo',
                'surname': 'bar',
                'email_address': 'user@domain.com',
                'msisdn': msisdn,
                'existing_password': 'password',
                '_account': True,
                })
            token_url = response.context['token_url']
            self.confirm(token_url)
            user_account = self.user_api.get_user_account()
            self.assertEqual(user_account.msisdn, '+27761234567')

    def test_update_msisdn_invalid(self):
        invalid = ['+123', '123', 'abc']
        for msisdn in invalid:
            response = self.client.post(reverse('account:details'), {
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
            user_account = self.user_api.get_user_account()
            self.assertEqual(user_account.msisdn, None)

    @staticmethod
    def extract_notification_messages(response):
        return [m.message for m in list(response.context['messages'])]

    def test_confirm_start_conversation(self):
        response = self.client.post(reverse('account:details'), {
            'name': 'foo',
            'surname': 'bar',
            'email_address': 'user@domain.com',
            'existing_password': 'password',
            'msisdn': '+27761234567',
            'confirm_start_conversation': True,
            '_account': True,
            })
        token_url = response.context['token_url']
        response = self.client.get(reverse('account:details'))

        notifications = self.extract_notification_messages(response)
        self.assertTrue(
            'Please confirm this change by clicking on the link that was '
            'just sent to your mailbox.' in notifications)

        user_account = self.user_api.get_user_account()
        self.assertFalse(user_account.confirm_start_conversation)

        [email] = mail.outbox
        self.assertTrue(token_url in email.body)

        response = self.confirm(token_url)
        notifications = self.extract_notification_messages(response)
        self.assertTrue('Your details are being updated' in notifications)

        user_account = self.user_api.get_user_account()
        self.assertTrue(user_account.confirm_start_conversation)

    def test_email_summary(self):
        user_account = self.user_api.get_user_account()
        response = self.client.post(reverse('account:details'), {
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
        notifications = self.extract_notification_messages(response)
        self.assertTrue('Your details are being updated' in notifications)

        user_account = self.user_api.get_user_account()
        self.assertEqual(user_account.email_summary, 'daily')

    def test_require_msisdn_if_confirm_start_conversation(self):
        response = self.client.post(reverse('account:details'), {
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


class EmailTestCase(VumiGoDjangoTestCase):
    use_riak = True

    def setUp(self):
        super(EmailTestCase, self).setUp()
        self.setup_api()
        self.setup_user_api()
        self.setup_client()

    def test_email_sending(self):
        response = self.client.post(reverse('account:details'), {
            '_email': True,
            'subject': 'foo',
            'message': 'bar',
            })
        self.assertRedirects(response, reverse('account:details'))
        [email] = mail.outbox
        self.assertEqual(email.subject, 'foo')
        self.assertEqual(email.from_email, self.django_user.email)
        self.assertTrue('bar' in email.body)

    def test_daily_account_summary(self):
        conv = self.create_conversation(
            started=True, conversation_type=u'bulk_message',
            name=u'Test Conversation')
        self.contact_store.new_contact(
            name=u'Contact', surname=u'One', msisdn=u"+27761234567")
        self.contact_store.new_contact(
            name=u'Contact', surname=u'Two', msisdn=u"+27761234567")

        self.add_messages_to_conv(5, conv, reply=True)
        # create a second conversation to test sorting
        self.create_conversation()

        # schedule the task
        send_user_account_summary(self.django_user)

        [email] = mail.outbox
        self.assertEqual(email.subject, 'Vumi Go Account Summary')
        self.assertEqual(email.from_email, settings.DEFAULT_FROM_EMAIL)
        self.assertEqual(email.recipients(), [self.django_user.email])
        self.assertTrue('number of contacts: 2' in email.body)
        self.assertTrue('number of unique contacts by contact number: 1'
                            in email.body)
        self.assertTrue('number of messages sent: 5' in email.body)
        self.assertTrue('number of messages received: 5' in email.body)
        self.assertTrue('Group Message' in email.body)
        self.assertTrue('Test Conversation' in email.body)
        self.assertTrue('Sent: 5 to 5 uniques.' in email.body)
        self.assertTrue('Received: 5 from 5 uniques.' in email.body)
        self.assertTrue('"Group Message" Sent: 5' in email.body)
        self.assertTrue('"Group Message" Received: 5' in email.body)

    def test_send_scheduled_account_summary_task(self):
        user_account = self.user_api.get_user_account()
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
