import requests

from django.http import HttpResponse

from go.conversation.view_definition import (
    ConversationViewDefinitionBase, ConversationTemplateView,
    EditConversationView)

from go.apps.jsbox.forms import JsboxForm, JsboxAppConfigFormset
from go.apps.jsbox.log import LogManager

from urlparse import urlparse, urlunparse


class CrossDomainXHRView(ConversationTemplateView):
    view_name = 'cross_domain_xhr'
    path_suffix = 'cross_domain_xhr/'
    csrf_exempt = True

    def get(self, request, conversation):
        return self.cross_domain_xhr(request)

    def post(self, request, conversation):
        return self.cross_domain_xhr(request)

    def cross_domain_xhr(self, request):
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
            url = url

        r = requests.get(url, auth=auth)
        return HttpResponse(r.text, status=r.status_code)


class JSBoxLogsView(ConversationTemplateView):
    view_name = 'jsbox_logs'
    path_suffix = 'jsbox_logs/'
    template_base = 'jsbox'

    def get(self, request, conversation):
        campaign_key = request.user_api.user_account_key
        log_manager = LogManager(request.user_api.api.redis)
        logs = log_manager.get_logs(campaign_key, conversation.key)
        logs = list(reversed(logs))
        return self.render_to_response({
            "conversation": conversation,
            "logs": logs,
        })


class EditJSBoxView(EditConversationView):
    edit_forms = (
        ('jsbox', JsboxForm),
        ('jsbox_app_config', JsboxAppConfigFormset),
    )


class ConversationViewDefinition(ConversationViewDefinitionBase):
    edit_view = EditJSBoxView

    extra_views = (
        CrossDomainXHRView,
        JSBoxLogsView,
    )
