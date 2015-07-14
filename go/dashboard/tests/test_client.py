import json

from go.vumitools.tests.helpers import djangotest_imports

with djangotest_imports(globals()):
    import requests

    from go.base.tests.helpers import GoDjangoTestCase, DjangoVumiApiHelper
    from go.dashboard.client import DiamondashApiError, DiamondashApiClient
    from go.dashboard.tests.utils import FakeDiamondashApiClient


class FakeResponse(object):
    def __init__(self, content="", status_code=200):
        self.status_code = status_code
        self.content = content

    def raise_for_status(self):
        pass


class FakeErrorResponse(object):
    def __init__(self, content, status_code=500):
        self.status_code = status_code
        self.content = content

    def raise_for_status(self):
        raise requests.exceptions.HTTPError(self.content)


class TestDashboardApiClient(GoDjangoTestCase):
    def setUp(self):
        self.vumi_helper = self.add_helper(DjangoVumiApiHelper())
        self.vumi_helper.patch_settings(
            DIAMONDASH_API_URL='http://diamondash.moc/api')

    def test_raw_request(self):
        self.vumi_helper.patch_settings(
            DIAMONDASH_API_USERNAME='username',
            DIAMONDASH_API_PASSWORD='password')

        resp = FakeResponse('spam', 201)

        def stubbed_request(method, url, data, auth):
            self.assertEqual(method, 'put')
            self.assertEqual(url, 'http://diamondash.moc/api/foo')
            self.assertEqual(data, 'bar')
            self.assertEqual(auth, ('username', 'password'))
            return resp

        self.monkey_patch(requests, 'request', stubbed_request)

        client = DiamondashApiClient()
        self.assertEqual(client.raw_request('put', 'foo', 'bar'), {
            'code': 201,
            'content': 'spam'
        })

    def test_raw_request_for_error_responses(self):
        resp = FakeErrorResponse(':(')
        self.monkey_patch(requests, 'request', lambda *a, **kw: resp)

        client = DiamondashApiClient()
        self.assertRaises(
            DiamondashApiError,
            client.raw_request,
            'put', 'foo', 'bar')

    def test_raw_request_no_auth(self):
        def stubbed_request(method, url, data, auth):
            self.assertEqual(auth, None)
            return FakeResponse()

        self.monkey_patch(requests, 'request', stubbed_request)

        client = DiamondashApiClient()
        client.raw_request('put', 'foo'),

    def test_request(self):
        self.vumi_helper.patch_settings(
            DIAMONDASH_API_USERNAME='username',
            DIAMONDASH_API_PASSWORD='password')

        resp = FakeResponse(json.dumps({
            'success': True,
            'data': {'spam': 'ham'}
        }))

        def stubbed_request(method, url, data, auth):
            self.assertEqual(method, 'put')
            self.assertEqual(url, 'http://diamondash.moc/api/foo')
            self.assertEqual(data, json.dumps({'bar': 'baz'}))
            self.assertEqual(auth, ('username', 'password'))
            return resp

        self.monkey_patch(requests, 'request', stubbed_request)

        client = DiamondashApiClient()
        self.assertEqual(
            client.request('put', 'foo', {'bar': 'baz'}),
            {'spam': 'ham'})

    def test_request_no_auth(self):
        def stubbed_request(method, url, data, auth):
            self.assertEqual(auth, None)
            return FakeResponse(json.dumps({'data': {}}))

        self.monkey_patch(requests, 'request', stubbed_request)

        client = DiamondashApiClient()
        client.request('put', 'foo', {}),

    def test_request_for_error_responses(self):
        resp = FakeErrorResponse(':(')
        self.monkey_patch(requests, 'request', lambda *a, **kw: resp)

        client = DiamondashApiClient()
        self.assertRaises(
            DiamondashApiError,
            client.request,
            'put', 'foo', 'bar')

    def test_make_api_url(self):
        client = DiamondashApiClient()

        self.assertEqual(
            client.make_api_url('dashboards'),
            'http://diamondash.moc/api/dashboards')

    def test_replace_dashboard(self):
        client = FakeDiamondashApiClient()
        client.replace_dashboard({'some': 'dashboard'})

        self.assertEqual(client.get_requests(), [{
            'method': 'put',
            'url': 'dashboards',
            'data': {'some': 'dashboard'},
        }])
