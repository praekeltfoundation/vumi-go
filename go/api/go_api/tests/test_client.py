import json

from django.conf import settings
from django.test import TestCase

from go.api.go_api import client

from mock import patch


class ClientTestCase(TestCase):
    @patch('requests.post')
    def test_rpc(self, mock_post):
        client.rpc('123', 'do_something', ['foo', 'bar'], id='abc')
        mock_post.assert_called_with(
            settings.GO_API_URL,
            auth=('session_id', '123'),
            data=json.dumps({
                'jsonrpc': '2.0',
                'id': 'abc',
                'params': ['foo', 'bar'],
                'method': 'routing_table',
            }))
