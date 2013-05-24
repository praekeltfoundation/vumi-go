import requests
from urlparse import urlparse, urlunparse

from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from django.shortcuts import render_to_response
from django.views.decorators.csrf import csrf_exempt

from go.conversation.base import ConversationViews
from go.apps.jsbox.forms import JsboxForm, JsboxAppConfigFormset
from go.apps.jsbox.log import LogManager
from go.utils import conversation_or_404


class JsboxConversationViews(ConversationViews):
    conversation_type = u'jsbox'
    conversation_display_name = u'Javascript App'
    conversation_initiator = None
    edit_conversation_forms = (
        ('jsbox', JsboxForm),
        ('jsbox_app_config', JsboxAppConfigFormset),
        )


@login_required
@csrf_exempt
def cross_domain_xhr(request):
    url = request.POST.get('url', None)

    parse_result = urlparse(url)
    if parse_result.username:
        auth = (parse_result.username, parse_result.password)
        url = urlunparse((parse_result.scheme,
                          ('%s:%s' % (parse_result.hostname, parse_result.port)
                           if parse_result.port
                           else parse_result.hostname),
                          parse_result.path,
                          parse_result.params,
                          parse_result.query,
                          parse_result.fragment))
    else:
        auth = None
        url = url

    r = requests.get(url, auth=auth)
    return HttpResponse(r.text, status=r.status_code)


@login_required
def jsbox_logs(request, conversation_key):
    campaign_key = request.user_api.user_account_key
    conversation = conversation_or_404(request.user_api, conversation_key)
    # TODO: find a better way to get a suitable redis instance
    redis = request.user_api.redis.sub_manager("jslogs")
    log_manager = LogManager(redis)
    logs = log_manager.get_logs(campaign_key, conversation_key)
    return render_to_response("", {
        "conversation": conversation,
        "jsbox_logs": reversed(logs),
    })
