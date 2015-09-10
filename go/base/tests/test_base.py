from go.vumitools.api import VumiApi, VumiUserApi
from go.vumitools.conversation.definition import ConversationDefinitionBase
from go.vumitools.tests.helpers import djangotest_imports

with djangotest_imports(globals()):
    from django.core.urlresolvers import reverse
    from django.contrib.auth import get_user_model
    from django.contrib.auth.models import Permission
    from django.core.paginator import Paginator

    from go.base import utils
    from go.base.tests.helpers import GoDjangoTestCase, DjangoVumiApiHelper
    from go.conversation.view_definition import ConversationViewDefinitionBase


class TestAuthentication(GoDjangoTestCase):

    def setUp(self):
        self.vumi_helper = self.add_helper(DjangoVumiApiHelper())
        self.user = self.vumi_helper.make_django_user().get_django_user()

    def test_user_account_created(self):
        """test that we have a user account"""
        api = self.vumi_helper.get_vumi_api()
        self.assertEqual(
            'user@domain.com',
            self.user.userprofile.get_user_account(api).username)

    def test_redirect_to_login(self):
        """test the authentication mechanism"""
        response = self.client.get(reverse('conversations:index'))
        self.assertRedirects(response, '%s?next=%s' % (
            reverse('auth_login'), reverse('conversations:index')))

    def test_login(self):
        self.client.login(username=self.user.email, password='password')
        response = self.client.get(reverse('conversations:index'))
        self.assertContains(response, 'Dashboard')

    def test_logged_out(self):
        """test logout & redirect after logout"""
        self.client.login(username=self.user.email, password='password')
        response = self.client.get(reverse('auth_logout'))
        response = self.client.get(reverse('conversations:index'))
        self.assertRedirects(response, '%s?next=%s' % (
            reverse('auth_login'), reverse('conversations:index')))


class FakeTemplateToken(object):
    def __init__(self, contents):
        self.contents = contents


class TestUtils(GoDjangoTestCase):

    def setUp(self):
        self.vumi_helper = self.add_helper(DjangoVumiApiHelper())
        self.user = self.vumi_helper.make_django_user().get_django_user()

    def test_vumi_api_for_user(self):
        user_api = utils.vumi_api_for_user(self.user)
        self.add_cleanup(user_api.close)
        self.assertTrue(isinstance(user_api, VumiUserApi))
        self.assertEqual(user_api.user_account_key,
                         self.user.get_profile().user_account)

    def test_vumi_api(self):
        vumi_api = utils.vumi_api()
        self.add_cleanup(vumi_api.close)
        self.assertTrue(isinstance(vumi_api, VumiApi))

    def test_padded_queryset(self):
        short_list = get_user_model().objects.all()[:1]
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

    def test_get_conversation_view_definition(self):
        view_def = utils.get_conversation_view_definition('bulk_message', None)
        conv_def = view_def._conv_def
        self.assertTrue(isinstance(view_def, ConversationViewDefinitionBase))
        self.assertTrue(isinstance(conv_def, ConversationDefinitionBase))
        self.assertEqual('bulk_message', conv_def.conversation_type)
