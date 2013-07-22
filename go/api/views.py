from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt

from go.api.go_api import client


import logging
logger = logging.getLogger(__name__)


@login_required
@csrf_exempt
@require_http_methods(['GET', 'POST'])
def go_api_proxy(request):
    return client.request(
        request.session.session_key,
        request.method,
        request.body)
