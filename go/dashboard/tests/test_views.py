import json

from go.base.tests.utils import VumiGoDjangoTestCase
from go.dashboard import client
from go.dashboard.tests.utils import FakeDiamondashApiClient


class DashboardViewsTestCase(VumiGoDjangoTestCase):
    def setUp(self):
        super(DashboardViewsTestCase, self).setUp()
        self.user = self.mk_django_user()
        self.diamondash_api = FakeDiamondashApiClient()

        self.monkey_patch(
            client,
            'get_diamondash_api',
            lambda: self.diamondash_api)

    def test_api_proxy(self):
        self.client.login(username=self.user.email, password='password')

        self.diamondash_api.set_raw_response(json.dumps({'bar': 'baz'}), 201)
        resp = self.client.get('/diamondash/api/foo')

        self.assertEqual(self.diamondash_api.get_requests(), [{
            'url': '/foo',
            'content': '',
            'method': 'GET',
        }])

        self.assertEqual(resp.content, json.dumps({'bar': 'baz'}))
        self.assertEqual(resp.status_code, 201)
