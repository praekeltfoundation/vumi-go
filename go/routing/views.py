import json

from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.conf import settings
import requests


def _get_routing_table(user_account_key, session_id):
    # TODO: Better Go API client.

    url = settings.GO_API_URL
    auth = ('session_id', session_id)
    req_data = {
        "params": [user_account_key],
        "jsonrpc": "2.0",
        "method": "routing_table",
        "id": None,
    }
    data = json.dumps(req_data)

    r = requests.post(url, auth=auth, data=data)

    model_data = {
        'campaign_id': user_account_key,
    }
    model_data.update(r.json['result'])

    return json.dumps(model_data)


@login_required
def routing(request):
    model_data = _get_routing_table(
        request.user_api.user_account_key, request.session.session_key)

    return render(request, 'routing.html', {
        'model_data': model_data,
    })
