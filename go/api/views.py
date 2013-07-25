from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
import requests


@login_required
@csrf_exempt
@require_http_methods(['GET', 'POST'])
def go_api_proxy(request):
    """
    Proxies client requests to the go api worker.

    NOTE: This is a straight passthrough to the api, no extra behaviour should
    be added.

    NOTE: This proxy is a fallback for dev purposes only. A more sensible
    proxying solution should be used in production (eg. haproxy).
    """

    headers = {}
    if 'HTTP_AUTHORIZATION' in request.META:
        headers['Authorization'] = request.META['HTTP_AUTHORIZATION']

    response = requests.request(
        request.method,
        settings.GO_API_URL,
        data=request.body,
        headers=headers)

    return HttpResponse(
        response.content,
        status=response.status_code,
        content_type=response.headers['content-type'])
