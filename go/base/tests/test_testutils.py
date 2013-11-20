import json
import requests

from go.vumitools.tests.utils import GoTestCase
from go.base.tests.utils import (
    FakeResponse, FakeRpcResponse, FakeRpcErrorResponse, FakeServer)


class TestFakeResponse(GoTestCase):
    def test_json_content(self):
        resp = FakeResponse(data={'foo': 'bar'})
        self.assertEqual(resp.json, {'foo': 'bar'})

    def test_plain_content(self):
        resp = FakeResponse(content='foo')
        self.assertEqual(resp.content, 'foo')

    def test_error_raising(self):
        resp = FakeResponse(code=500)
        self.assertRaises(requests.exceptions.HTTPError, resp.raise_for_status)


class TestFakeRpcResponse(GoTestCase):
    def test_rpc_response_data(self):
        resp = FakeRpcResponse(id='some-id', result={'foo': 'bar'})
        self.assertEqual(resp.json, {
            'jsonrpc': '2.0',
            'id': 'some-id',
            'result': {'foo': 'bar'}
        })


class TestFakeRpcErrorResponse(GoTestCase):
    def test_rpc_error_response_data(self):
        resp = FakeRpcErrorResponse(id='some-id', error=':(')
        self.assertEqual(resp.json, {
            'jsonrpc': '2.0',
            'id': 'some-id',
            'result': None,
            'error': ':('
        })


class TestFakeServer(GoTestCase):
    def setUp(self):
        super(TestFakeServer, self).setUp()

        self.patch(requests, 'get', lambda *a, **kw: 'get')
        self.patch(requests, 'post', lambda *a, **kw: 'post')
        self.patch(requests, 'put', lambda *a, **kw: 'put')
        self.patch(requests, 'head', lambda *a, **kw: 'head')
        self.patch(requests, 'patch', lambda *a, **kw: 'patch')
        self.patch(requests, 'options', lambda *a, **kw: 'options')
        self.patch(requests, 'delete', lambda *a, **kw: 'delete')

        self.server = FakeServer(r'^http://some.place')

    def tearDown(self):
        super(TestFakeServer, self).tearDown()
        self.server.tear_down()

    def test_request_catching(self):
        requests.request('get', 'http://some.place')
        requests.get('http://some.place')
        requests.post('http://some.place')
        requests.put('http://some.place')
        requests.head('http://some.place')
        requests.patch('http://some.place')
        requests.options('http://some.place')
        requests.delete('http://some.place')

        self.assertEqual(self.server.get_requests(), [
            {'method': 'get', 'url': 'http://some.place'},
            {'method': 'get', 'url': 'http://some.place'},
            {'method': 'post', 'url': 'http://some.place'},
            {'method': 'put', 'url': 'http://some.place'},
            {'method': 'head', 'url': 'http://some.place'},
            {'method': 'patch', 'url': 'http://some.place'},
            {'method': 'options', 'url': 'http://some.place'},
            {'method': 'delete', 'url': 'http://some.place'}])

    def test_request_catching_for_json_data_loading(self):
        requests.put('http://some.place', data=json.dumps({'foo': 'bar'}))
        self.assertEqual(self.server.get_requests(), [{
            'method': 'put',
            'url': 'http://some.place',
            'data': {'foo': 'bar'},
        }])

    def test_request_response_setting(self):
        resp = FakeResponse()
        self.server.set_response(resp)

        self.assertEqual(resp, requests.request('get', 'http://some.place'))
        self.assertEqual(resp, requests.get('http://some.place'))
        self.assertEqual(resp, requests.post('http://some.place'))
        self.assertEqual(resp, requests.put('http://some.place'))
        self.assertEqual(resp, requests.head('http://some.place'))
        self.assertEqual(resp, requests.patch('http://some.place'))
        self.assertEqual(resp, requests.options('http://some.place'))
        self.assertEqual(resp, requests.delete('http://some.place'))

    def test_request_bypassing(self):
        requests.request('get', 'http://other.place')
        requests.get('http://other.place')
        requests.post('http://other.place')
        requests.put('http://other.place')
        requests.head('http://other.place')
        requests.patch('http://other.place')
        requests.options('http://other.place')
        requests.delete('http://other.place')
        self.assertEqual(self.server.get_requests(), [])

    def test_request_response_bypassing(self):
        self.assertEqual('get', requests.request('get', 'http://other.place'))
        self.assertEqual('get', requests.get('http://other.place'))
        self.assertEqual('post', requests.post('http://other.place'))
        self.assertEqual('put', requests.put('http://other.place'))
        self.assertEqual('head', requests.head('http://other.place'))
        self.assertEqual('patch', requests.patch('http://other.place'))
        self.assertEqual('options', requests.options('http://other.place'))
        self.assertEqual('delete', requests.delete('http://other.place'))
