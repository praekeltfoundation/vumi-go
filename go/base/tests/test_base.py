from django.test.client import Client
from django.core.urlresolvers import reverse
from django.contrib.auth.models import User, Permission
from django.core.paginator import Paginator

from go.base.tests.utils import VumiGoDjangoTestCase
from go.base import utils


class AuthenticationTestCase(VumiGoDjangoTestCase):

    def setUp(self):
        super(AuthenticationTestCase, self).setUp()
        self.setup_api()
        self.user = self.mk_django_user()
        self.client = Client()

    def test_user_account_created(self):
        """test that we have a user account"""
        self.assertEqual('username',
                         self.user.userprofile.get_user_account().username)

    def test_redirect_to_login(self):
        """test the authentication mechanism"""
        response = self.client.get(reverse('conversations:index'))
        self.assertRedirects(response, '%s?next=%s' % (
            reverse('auth_login'), reverse('conversations:index')))

    def test_login(self):
        self.client.login(username=self.user.username, password='password')
        response = self.client.get(reverse('conversations:index'))
        self.assertContains(response, '%s %s' % (self.user.first_name,
            self.user.last_name),)

    def test_logged_out(self):
        """test logout & redirect after logout"""
        self.client.login(username=self.user.username, password='password')
        response = self.client.get(reverse('auth_logout'))
        response = self.client.get(reverse('conversations:index'))
        self.assertRedirects(response, '%s?next=%s' % (
            reverse('auth_login'), reverse('conversations:index')))


class FakeTemplateToken(object):
    def __init__(self, contents):
        self.contents = contents


class UtilsTestCase(VumiGoDjangoTestCase):

    def setUp(self):
        super(UtilsTestCase, self).setUp()
        self.setup_api()
        self.user = self.mk_django_user()

    def test_padded_queryset(self):
        short_list = User.objects.all()[:1]
        padded_list = utils.padded_queryset(short_list)
        expected_list = list(short_list) + [None, None, None, None, None]
        self.assertEqual(padded_list, expected_list)

    def test_padded_queryset_limiting(self):
        long_list = Permission.objects.all()
        self.assertTrue(long_list.count() > 6)
        padded_list = utils.padded_queryset(long_list)
        self.assertEqual(len(padded_list), 6)

    def test_page_range_window(self):
        paginator = Paginator(range(100), 5)
        self.assertEqual(utils.page_range_window(paginator.page(1), 5),
            [1, 2, 3, 4, 5, 6, 7, 8, 9])
        self.assertEqual(utils.page_range_window(paginator.page(5), 5),
            [1, 2, 3, 4, 5, 6, 7, 8, 9])
        self.assertEqual(utils.page_range_window(paginator.page(9), 5),
            [5, 6, 7, 8, 9, 10, 11, 12, 13])
        self.assertEqual(utils.page_range_window(paginator.page(20), 5),
            [12, 13, 14, 15, 16, 17, 18, 19, 20])

        paginator = Paginator(range(3), 5)
        self.assertEqual(utils.page_range_window(paginator.page(1), 5),
            [1])

        paginator = Paginator(range(3), 3)
        self.assertEqual(utils.page_range_window(paginator.page(1), 5),
            [1])

        paginator = Paginator(range(4), 3)
        self.assertEqual(utils.page_range_window(paginator.page(1), 5),
            [1, 2])
