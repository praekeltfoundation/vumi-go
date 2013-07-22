#import json

from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt

#from django.conf import settings
#import requests

from go.api.go_api import client


import logging
logger = logging.getLogger(__name__)


@login_required
@csrf_exempt
@require_http_methods(['GET', 'POST'])
def go_api_proxy(request):
    response = client.request(
        request.session.session_key,
        data=request.body,
        method=request.method)

    return HttpResponse(
        response.content,
        status=response.status_code,
        content_type=response.headers['content-type'])
