import urllib

from django.test.client import Client
from django.core.urlresolvers import reverse

from go.apps.tests.base import DjangoGoApplicationTestCase
from go.base.token_manager import TokenManager


class TokenManagerTestCase(DjangoGoApplicationTestCase):
    use_riak = False

    def setUp(self):
        super(TokenManagerTestCase, self).setUp()
        self.client = Client()
        self.redis = self.get_redis_manager()
        self.tm = TokenManager(self.redis.sub_manager('token_manager'))
        self.user = self.mk_django_user()

    def test_token_generation(self):
        token = self.tm.generate('/some/path/', lifetime=10)
        token_data = self.tm.get(token)
        self.assertEqual(len(token), 6)
        self.assertEqual(token_data['user_id'], '')
        self.assertEqual(token_data['redirect_to'], '/some/path/')
        self.assertTrue(token_data['system_token'])

    def test_token_provided(self):
        token = self.tm.generate('/some/path/', lifetime=10,
                                    token=('to', 'ken'))
        self.assertEqual(token, 'to')
        token_data = self.tm.get(token)
        self.assertEqual(token_data['system_token'], 'ken')

    def test_unknown_token(self):
        self.assertEqual(self.tm.get('foo'), {})

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
            response['Location'].endswith('/path/?token=%s%s%s' % (
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

    def test_token_verify(self):
        token = self.tm.generate('/foo/', token=('to', 'ken'))
        self.assertEqual(self.tm.get(token, verify='bar'), {})
        self.assertEqual(self.tm.get(token, verify='ken'), {
            'user_id': '',
            'system_token': 'ken',
            'redirect_to': '/foo/',
            })

    def test_token_delete(self):
        token = self.tm.generate('/foo/')
        self.assertTrue(self.tm.get(token))
        self.assertTrue(self.tm.delete(token))
        self.assertFalse(self.tm.get(token))
