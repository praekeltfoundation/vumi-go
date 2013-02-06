import requests

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
    
    r = requests.get(url)
    return HttpResponse(r.text, status=r.status_code)