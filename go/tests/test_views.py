from django.core.urlresolvers import reverse

from django.contrib.flatpages.models import FlatPage
from django.contrib.sites.models import Site

from go.base.tests.helpers import GoDjangoTestCase, DjangoVumiApiHelper


class TestNav(GoDjangoTestCase):
    def setUp(self):
        self.vumi_helper = self.add_helper(DjangoVumiApiHelper())
        self.user_helper = self.vumi_helper.make_django_user()
        self.superuser_helper = self.vumi_helper.make_django_user(
            email='superuser@example.com', superuser=True)

    def test_right_nav_dropdown_staff(self):
        client = self.vumi_helper.get_client('superuser@example.com')
        response = client.get(reverse('home'), follow=True)
        self.assertContains(response, '<a href="/admin/">Site Admin</a>')
        self.assertContains(
            response, '<a href="/account/details/">Details</a>')

    def test_right_nav_dropdown_authenticated(self):
        client = self.vumi_helper.get_client()
        response = client.get(reverse('home'), follow=True)
        self.assertNotContains(response, '>Site Admin<')
        self.assertContains(
            response, '<a href="/account/details/">Details</a>')

    def test_right_nav_dropdown_unauthenticated(self):
        client = self.vumi_helper.get_client()
        client.logout()
        response = client.get(reverse('home'), follow=True)
        self.assertNotContains(response, '>Site Admin<')
        self.assertNotContains(response, '>Details<')


class TestHelpViews(GoDjangoTestCase):

    def setUp(self):
        self.vumi_helper = self.add_helper(DjangoVumiApiHelper())
        self.user_helper = self.vumi_helper.make_django_user()
        self.client = self.vumi_helper.get_client()

    def mk_help(self):
        page = FlatPage(title='Help', content="Wisdom", url="/help/")
        page.save()
        for site in Site.objects.all():
            page.sites.add(site)

    def test_help_authenticated(self):
        """The help view should be accessible when logged in."""
        self.mk_help()
        response = self.client.get(reverse('help'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Help')
        self.assertContains(response, 'Dashboard')
        self.assertContains(response, 'Contacts')
        self.assertContains(response, 'Account')
        self.assertContains(response, 'credits')

    def test_help_not_authenticated(self):
        """The help view should be accessible when not logged in."""
        self.mk_help()
        self.client.logout()
        response = self.client.get(reverse('help'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Help')
        self.assertNotContains(response, 'Dashboard')
        self.assertNotContains(response, 'Contacts')
        self.assertNotContains(response, 'Account')
        self.assertNotContains(response, 'credits')


class TestApp(GoDjangoTestCase):
    def setUp(self):
        self.vumi_helper = self.add_helper(DjangoVumiApiHelper())
        self.user_helper = self.vumi_helper.make_django_user()
        self.client = self.vumi_helper.get_client()

    def test_google_analytics(self):
        response = self.client.get(reverse('home'), follow=True)
        self.assertContains(response, 'TEST-GA-UA')
        self.assertContains(response, 'analytics.js')

    # TODO: remove once #1029 is done

    def test_aria_footer(self):
        response = self.client.get(reverse('home'), follow=True)
        self.assertContains(response, 'role="contentinfo"')

    def test_aria_banner_and_nav(self):
        response = self.client.get(reverse('home'), follow=True)
        self.assertContains(response, 'role="banner"')
        self.assertContains(response, 'role="navigation"')
