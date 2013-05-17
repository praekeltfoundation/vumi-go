import requests
from urlparse import urlparse

from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt

from go.conversation.base import ConversationViews
from go.apps.jsbox.forms import JsboxForm, JsboxAppConfigFormset


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
    else:
        auth = None

    r = requests.get(url, auth=auth)
    return HttpResponse(r.text, status=r.status_code)
