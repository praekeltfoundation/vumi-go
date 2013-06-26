import json

from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.conf import settings
import requests


@login_required
def routing(request):
    # TODO: Better Go API client.

    url = settings.GO_API_URL
    auth = ('session_id', request.COOKIES['sessionid'])
    req_data = {
        "params": [request.user_api.user_account_key],
        "jsonrpc": "2.0",
        "method": "routing_table",
        "id": None,
    }
    data = json.dumps(req_data)

    r = requests.post(url, auth=auth, data=data)

    model_data = {
        'campaign_id': request.user_api.user_account_key,
    }
    model_data.update(r.json['result'])

    return render(request, 'routing.html', {
        'model_data': json.dumps(model_data),
    })
