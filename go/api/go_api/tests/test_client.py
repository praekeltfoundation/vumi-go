import json

from django.conf import settings

from go.api.go_api import client
from go.base.tests.helpers import GoDjangoTestCase

from mock import patch


class TestClient(GoDjangoTestCase):
    @patch('requests.post')
    def test_rpc(self, mock_req):
        client.rpc('123', 'do_something', ['foo', 'bar'], id='abc')

        mock_req.assert_called_with(
            settings.GO_API_URL,
            auth=('session_id', '123'),
            data=json.dumps({
                'jsonrpc': '2.0',
                'id': 'abc',
                'params': ['foo', 'bar'],
                'method': 'do_something',
            }))
