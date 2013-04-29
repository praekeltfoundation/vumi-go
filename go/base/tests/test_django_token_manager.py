import urllib

from django.test.client import Client
from django.core.urlresolvers import reverse
from django.contrib import messages

from go.apps.tests.base import DjangoGoApplicationTestCase
from go.vumitools.token_manager import TokenManager
from go.base.django_token_manager import DjangoTokenManager


class DjangoTokenManagerTestCase(DjangoGoApplicationTestCase):

    use_riak = False

    def setUp(self):
        super(DjangoTokenManagerTestCase, self).setUp()
        self.client = Client()
        self.redis = self.get_redis_manager()
        token_manager = TokenManager(
                        self.redis.sub_manager('token_manager'))
        self.user = self.mk_django_user()
        self.tm = DjangoTokenManager(token_manager)

    def test_generate_callback(self):
        token = self.tm.generate_callback_token('/foo/', 'It worked',
            callback_for_test, callback_args=['arg'],
            callback_kwargs={'kwarg': 'kwarg'}, message_level=messages.SUCCESS,
            user_id=self.user.pk)
        token_data = self.tm.get(token)
        self.assertEqual(token_data['redirect_to'], reverse('token_task'))
        self.assertEqual(token_data['user_id'], str(self.user.pk))
        self.assertEqual(token_data['extra_params'], {
            'callback_args': ['arg'],
            'callback_kwargs': {'kwarg': 'kwarg'},
            'callback_name': '%s.%s' % (callback_for_test.__module__,
                                        callback_for_test.__name__),
            'return_to': '/foo/',
            'message_level': messages.SUCCESS,
            'message': 'It worked',
            })

    def test_url_for_token(self):
        url = self.tm.url_for_token('foo')
        self.assertTrue(url.endswith(reverse('token',
            kwargs={'token': 'foo'})))

    def test_token_require_login(self):
        token = self.tm.generate('/path/', user_id=self.user.pk)
        token_url = reverse('token', kwargs={'token': token})
        response = self.client.get(token_url)
        self.assertRedirects(response,
            '%s?%s' % (reverse('auth_login'), urllib.urlencode({
                        'next': reverse('token', kwargs={'token': token}),
                        })))

    def test_token_with_login(self):
        token = self.tm.generate('/path/', user_id=self.user.pk)
        token_url = reverse('token', kwargs={'token': token})
        token_data = self.tm.get(token)
        self.client.login(username='username', password='password')
        response = self.client.get(token_url)
        self.assertTrue(
            response['Location'].endswith('/path/?token=%s-%s%s' % (
                len(token), token, token_data['system_token'])))

    def test_token_with_invalid_login(self):
        token = self.tm.generate('/path/', user_id=-1)
        token_url = reverse('token', kwargs={'token': token})
        self.client.login(username='username', password='password')
        response = self.client.get(token_url)
        self.assertRedirects(response,
            '%s?%s' % (reverse('auth_login'), urllib.urlencode({
                        'next': reverse('token', kwargs={'token': token}),
                        })))

    def test_invalid_token(self):
        token = self.tm.generate('/foo/', user_id=self.user.pk)
        token_url = reverse('token', kwargs={'token': token})
        response = self.client.get(token_url)
        self.assertTrue(response.status_code, 404)


def callback_for_test(arg, kwarg='kwarg'):
    """
    This is just here to so the test_generate_callback has an actual
    callback to refer to.
    """
    pass
