from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt

from go.dashboard import client


@login_required
@csrf_exempt
@require_http_methods(['GET'])
def diamondash_api_proxy(request):
    """
    Proxies client snapshot requests to diamondash.

    NOTE: This proxy is a fallback for dev purposes only. A more sensible
    proxying solution should be used in production (eg. haproxy).
    """
    api = client.get_diamondash_api()
    _, url = request.path.split('/diamondash/api', 1)
    response = api.raw_request(request.method, url, content=request.body)

    return HttpResponse(
        response['content'],
        status=response['code'],
        content_type='application/json')
