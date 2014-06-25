from django.core.urlresolvers import reverse

from go.base.tests.helpers import GoDjangoTestCase, DjangoVumiApiHelper


class TestLoginAs(GoDjangoTestCase):

    def setUp(self):
        self.vumi_helper = self.add_helper(DjangoVumiApiHelper())
        self.superuser_helper = self.vumi_helper.make_django_user(
            superuser=True, email='superuser@example.com')
        self.user_helper_1 = self.vumi_helper.make_django_user(
            email='user1@example.com')
        self.user_helper_2 = self.vumi_helper.make_django_user(
            email='user2@example.com')

        self.superuser_client = self.vumi_helper.get_client(
            username='superuser@example.com')
        self.user_client_1 = self.vumi_helper.get_client(
            username='user1@example.com')

    def test_successful_login_as(self):
        """
        Superusers should be able to use login-as.
        """
        user_2_pk = self.user_helper_2.get_django_user().pk
        response = self.superuser_client.get(
            reverse('loginas-user-login', kwargs={'user_id': str(user_2_pk)}))
        self.assertRedirects(response, reverse('home'), target_status_code=302)
        self.assertEqual(response.client.session.get('_go_user_account_key'),
                         'test-2-user')

    def test_failed_login_as(self):
        """
        Ordinary users should not be able to use login-as.
        """
        user_2_pk = self.user_helper_2.get_django_user().pk
        response = self.user_client_1.get(
            reverse('loginas-user-login', kwargs={'user_id': str(user_2_pk)}))
        self.assertRedirects(response, reverse('home'), target_status_code=302)
        self.assertEqual(response.client.session.get('_go_user_account_key'),
                         'test-1-user')
