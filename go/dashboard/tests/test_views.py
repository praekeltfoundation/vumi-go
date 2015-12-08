import json

from go.vumitools.tests.helpers import djangotest_imports

with djangotest_imports(globals()):
    from go.base.tests.helpers import GoDjangoTestCase, DjangoVumiApiHelper
    from go.dashboard import client
    from go.dashboard.tests.utils import FakeDiamondashApiClient


class DashboardViewsTestCase(GoDjangoTestCase):
    def setUp(self):
        self.vumi_helper = self.add_helper(DjangoVumiApiHelper())
        self.user_helper = self.vumi_helper.make_django_user()
        self.client = self.vumi_helper.get_client()

        self.diamondash_api = FakeDiamondashApiClient()
        self.monkey_patch(
            client, 'get_diamondash_api', lambda: self.diamondash_api)

    def test_api_proxy(self):
        self.diamondash_api.set_raw_response(json.dumps({'bar': 'baz'}), 201)
        resp = self.client.get('/diamondash/api/foo')

        self.assertEqual(self.diamondash_api.get_requests(), [{
            'url': '/foo',
            'content': '',
            'method': 'GET',
        }])

        self.assertEqual(resp.content, json.dumps({'bar': 'baz'}))
        self.assertEqual(resp.status_code, 201)

    def test_api_proxy_error(self):
        self.diamondash_api.set_error_response(404, "Bad horse")
        resp = self.client.get('/diamondash/api/foo')

        self.assertEqual(self.diamondash_api.get_requests(), [{
            'url': '/foo',
            'content': '',
            'method': 'GET',
        }])

        self.assertEqual(json.loads(resp.content), {
            "message": "Bad horse",
            "success": False,
        })
        self.assertEqual(resp.status_code, 404)
