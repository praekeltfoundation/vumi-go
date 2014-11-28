import json

from django.shortcuts import render
from django.contrib.auth.decorators import login_required

from go.api.go_api import client
from go.api.go_api.client import GoApiError


@login_required
def routing(request):
    r = client.rpc(
        request.session.session_key,
        'routing_table',
        [request.user_api.user_account_key])

    if r.status_code != 200:
        raise GoApiError(
            "Failed to load routing table from Go API:"
            " (%r) %r." % (r.status_code, r.text))

    model_data = {'campaign_id': request.user_api.user_account_key}
    model_data.update(r.json()['result'])

    return render(request, 'routing.html', {
        'session_id': request.session.session_key,
        'model_data': json.dumps(model_data),
    })
