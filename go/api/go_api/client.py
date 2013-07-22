import json

from django.conf import settings
import requests


def rpc(session_id, method, params, id=None):
    auth = ('session_id', session_id)

    req_data = {
        "jsonrpc": "2.0",
        "id": id,
        "params": params,
        "method": "routing_table",
    }
    data = json.dumps(req_data)

    return requests.post(settings.GO_API_URL, auth=auth, data=data)
