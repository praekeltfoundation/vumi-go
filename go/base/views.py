import requests

from django.shortcuts import render
from django.http import HttpResponse

from urlparse import urlparse, urlunparse


def todo(request):  # pragma: no cover
    return render(request, 'base/todo.html', {
    })


def cross_domain_xhr(request):
    url = request.POST.get('url', None)

    parse_result = urlparse(url)
    if parse_result.username:
        auth = (parse_result.username, parse_result.password)
        url = urlunparse(
            (parse_result.scheme,
             ('%s:%s' % (parse_result.hostname, parse_result.port)
              if parse_result.port
              else parse_result.hostname),
             parse_result.path,
             parse_result.params,
             parse_result.query,
             parse_result.fragment))
    else:
        auth = None

    response = requests.get(url, auth=auth)

    return HttpResponse(
        response.content,
        status=response.status_code)
