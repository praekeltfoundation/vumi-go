"""Test for go.base.utils."""

from mock import patch, Mock
from django.core.urlresolvers import reverse

from go.base.tests.utils import VumiGoDjangoTestCase


class BaseViewsTestCase(VumiGoDjangoTestCase):
    def setUp(self):
        super(BaseViewsTestCase, self).setUp()
        self.setup_user_api()
        self.setup_client()

    def cross_domain_xhr(self, url):
        return self.client.post(reverse('cross_domain_xhr'), {'url': url})

    @patch('requests.get')
    def test_cross_domain_xhr(self, mocked_get):
        mocked_get.return_value = Mock(content='foo', status_code=200)
        response = self.cross_domain_xhr('http://domain.com')
        [call] = mocked_get.call_args_list
        args, kwargs = call
        self.assertEqual(args, ('http://domain.com',))
        self.assertEqual(kwargs, {'auth': None})
        self.assertTrue(mocked_get.called)
        self.assertEqual(response.content, 'foo')
        self.assertEqual(response.status_code, 200)

    @patch('requests.get')
    def test_basic_auth_cross_domain_xhr(self, mocked_get):
        mocked_get.return_value = Mock(content='foo', status_code=200)
        response = self.cross_domain_xhr('http://username:password@domain.com')
        [call] = mocked_get.call_args_list
        args, kwargs = call
        self.assertEqual(args, ('http://domain.com',))
        self.assertEqual(kwargs, {'auth': ('username', 'password')})
        self.assertTrue(mocked_get.called)
        self.assertEqual(response.content, 'foo')
        self.assertEqual(response.status_code, 200)

    @patch('requests.get')
    def test_basic_auth_cross_domain_xhr_with_https_and_port(self, mocked_get):
        mocked_get.return_value = Mock(content='foo', status_code=200)
        response = self.cross_domain_xhr(
            'https://username:password@domain.com:443/foo')
        [call] = mocked_get.call_args_list
        args, kwargs = call
        self.assertEqual(args, ('https://domain.com:443/foo',))
        self.assertEqual(kwargs, {'auth': ('username', 'password')})
        self.assertTrue(mocked_get.called)
        self.assertEqual(response.content, 'foo')
        self.assertEqual(response.status_code, 200)
