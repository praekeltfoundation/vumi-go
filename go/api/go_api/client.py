import json

from django.conf import settings
import requests


class GoApiError(Exception):
    """Raised when a call to the Go API fails."""


def request(session_id, data='', method='GET'):
    return requests.request(
        method,
        settings.GO_API_URL,
        auth=('session_id', session_id),
        data=data)


def rpc(session_id, method, params, id=None):
    return request(session_id, method='POST', data=json.dumps({
        'jsonrpc': '2.0',
        'id': id,
        'params': params,
        'method': method,
    }))
