from go.vumitools.tests.helpers import djangotest_imports

with djangotest_imports(globals()):
    from django.core.urlresolvers import reverse

    from go.base.tests.helpers import GoDjangoTestCase, DjangoVumiApiHelper


class TestLoginAs(GoDjangoTestCase):

    def setUp(self):
        self.vumi_helper = self.add_helper(DjangoVumiApiHelper())
        self.superuser_helper = self.vumi_helper.make_django_user(
            superuser=True, email='superuser@example.com')
        self.ordinary_user_helper = self.vumi_helper.make_django_user(
            email='ordinary_user@example.com')
        self.target_user_helper = self.vumi_helper.make_django_user(
            email='loginas_target@example.com')

        self.superuser_client = self.vumi_helper.get_client(
            username='superuser@example.com')
        self.ordinary_user_client = self.vumi_helper.get_client(
            username='ordinary_user@example.com')

    def test_successful_login_as(self):
        """
        Superusers should be able to use login-as.
        """
        target_user_pk = self.target_user_helper.get_django_user().pk
        response = self.superuser_client.get(
            reverse('loginas-user-login',
                    kwargs={'user_id': str(target_user_pk)})
        )
        self.assertRedirects(response, reverse('home'), target_status_code=302)
        self.assertEqual(response.client.session.get('_go_user_account_key'),
                         self.target_user_helper.account_key)

    def test_failed_login_as(self):
        """
        Ordinary users should not be able to use login-as.
        """
        target_user_pk = self.target_user_helper.get_django_user().pk
        response = self.ordinary_user_client.get(
            reverse('loginas-user-login',
                    kwargs={'user_id': str(target_user_pk)})
        )
        self.assertRedirects(response, reverse('home'), target_status_code=302)
        self.assertEqual(response.client.session.get('_go_user_account_key'),
                         self.ordinary_user_helper.account_key)
