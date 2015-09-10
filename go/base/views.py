import requests

from django.shortcuts import render
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required

from go.vumitools.utils import extract_auth_from_url


def todo(request):  # pragma: no cover
    return render(request, 'base/todo.html', {
    })


@login_required
def cross_domain_xhr(request):
    auth, url = extract_auth_from_url(request.POST.get('url', None))
    response = requests.get(url, auth=auth)

    return HttpResponse(
        response.content,
        status=response.status_code)
