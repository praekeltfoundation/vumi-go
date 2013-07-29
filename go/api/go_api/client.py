import json

from django.conf import settings
import requests


class GoApiError(Exception):
    """Raised when a call to the Go API fails."""


def rpc(session_id, method, params, id=None):
    return requests.post(
        settings.GO_API_URL,
        auth=('session_id', session_id),
        data=json.dumps({
            'jsonrpc': '2.0',
            'id': id,
            'params': params,
            'method': method,
        }))
