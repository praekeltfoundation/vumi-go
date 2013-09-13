from go.conversation.view_definition import (
    ConversationViewDefinitionBase, ConversationTemplateView,
    EditConversationView)

from go.apps.jsbox.forms import JsboxForm, JsboxAppConfigFormset
from go.apps.jsbox.log import LogManager


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
        JSBoxLogsView,
    )
