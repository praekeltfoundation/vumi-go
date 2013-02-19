import urllib

from django.test.client import Client
from django.core.urlresolvers import reverse
from django.contrib import messages

from go.apps.tests.base import DjangoGoApplicationTestCase
from go.base.token_manager import (TokenManager, InvalidToken, MalformedToken,
                                    TokenManagerException, DjangoTokenManager)

from mock import patch, Mock


class BaseTokenManagerTestCase(DjangoGoApplicationTestCase):
    use_riak = False
    token_manager_class = TokenManager

    def setUp(self):
        super(BaseTokenManagerTestCase, self).setUp()
        self.client = Client()
        self.redis = self.get_redis_manager()
        self.tm = self.token_manager_class(
            self.redis.sub_manager('token_manager'))
        self.user = self.mk_django_user()


class DefaultTokenManagerTestCase(BaseTokenManagerTestCase):

    def test_token_generation(self):
        token = self.tm.generate('/some/path/', lifetime=10)
        token_data = self.tm.get(token)
        self.assertEqual(len(token), 6)
        self.assertEqual(token_data['user_id'], '')
        self.assertEqual(token_data['redirect_to'], '/some/path/')
        self.assertTrue(token_data['system_token'])
        self.assertEqual(token_data['extra_params'], {})

    def test_token_provided(self):
        token = self.tm.generate('/some/path/', lifetime=10,
                                    token=('to', 'ken'))
        self.assertEqual(token, 'to')
        token_data = self.tm.get(token)
        self.assertEqual(token_data['system_token'], 'ken')

    def test_unknown_token(self):
        self.assertEqual(self.tm.get('foo'), None)

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

    def test_malformed_token(self):
        self.assertRaises(MalformedToken, self.tm.verify_get,
                            'A-token-starting-with-a-digit')

    def test_token_verify(self):
        token = self.tm.generate('/foo/', token=('to', 'ken'))
        self.assertRaises(InvalidToken, self.tm.get, token, verify='bar')
        self.assertEqual(self.tm.get(token, verify='ken'), {
            'user_id': '',
            'system_token': 'ken',
            'redirect_to': '/foo/',
            'extra_params': {},
            })

    def test_token_delete(self):
        token = self.tm.generate('/foo/')
        self.assertTrue(self.tm.get(token))
        self.assertTrue(self.tm.delete(token))
        self.assertFalse(self.tm.get(token))

    def test_token_extra_params(self):
        extra_params = {'one': 'two', 'three': 4}
        token = self.tm.generate('/foo/', extra_params=extra_params)
        token_data = self.tm.get(token)
        self.assertEqual(token_data['extra_params'], extra_params)

    def test_reuse_existing_token(self):
        token = ('to', 'ken')
        self.tm.generate('/foo/', token=token)
        self.assertRaises(TokenManagerException, self.tm.generate, '/foo/',
                            token=token)

    def test_race_condition(self):
        # claim these
        self.tm.generate('/foo/', token=('to1', 'ken'))
        self.tm.generate('/foo/', token=('to2', 'ken'))
        # patch the generate command to first return the ones that already
        # exist it should, continue trying until an un-used token is found
        with patch.object(TokenManager, 'generate_token') as mock:
            mock.side_effect = [('to1', 'ken'), ('to2', 'ken'), ('to3', 'ken')]
            user_token = self.tm.generate('/foo/')
        self.assertEqual(user_token, 'to3')


def callback_for_test(arg, kwarg='kwarg'):
    pass


class DjangoTokenManagerTestCase(BaseTokenManagerTestCase):

    token_manager_class = DjangoTokenManager

    def test_generate_callback(self):
        token = self.tm.generate_callback('/foo/', 'It worked',
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
