import json

from django.forms import Form

from go.dashboard.dashboard import ConversationReportsLayout
from go.conversation.view_definition import (
    ConversationViewDefinitionBase, ConversationReportsView,
    ConversationTemplateView, EditConversationView)

from go.apps.jsbox.forms import JsboxForm, JsboxAppConfigFormset
from go.apps.jsbox.log import LogManager


class JSBoxReportsView(ConversationReportsView):
    def _get_reports_config(self, conversation):
        app_config = conversation.config.get('jsbox_app_config', {})
        reports_config = app_config.get('reports', {}).get('value', 'null')
        return json.loads(reports_config)

    def build_layout(self, conversation):
        """
        Returns a conversation's dashboard widget data.
        Override to specialise dashboard building.
        """
        reports_config = self._get_reports_config(conversation)
        if reports_config is None:
            return super(JSBoxReportsView, self).build_layout(conversation)

        layout_config = reports_config.get('layout')
        layout = ConversationReportsLayout(conversation, layout_config)
        return layout


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
    template_base = 'jsbox'

    edit_forms = (
        ('jsbox', JsboxForm),
        ('jsbox_app_config', JsboxAppConfigFormset),
    )

    def get(self, request, conversation):
        edit_forms = dict(self.make_forms_dict(conversation))

        return self.render_to_response({
            'conversation': conversation,
            'jsbox_form': edit_forms['jsbox'],
            'jsbox_app_config_forms': edit_forms['jsbox_app_config'],
            'edit_forms_media': self.sum_media(edit_forms.values())
        })


class SendJsboxForm(Form):
    # TODO: Something better than this?
    pass


class ConversationViewDefinition(ConversationViewDefinitionBase):
    edit_view = EditJSBoxView

    extra_views = (
        JSBoxLogsView,
        JSBoxReportsView,
    )

    action_forms = {
        'send_jsbox': SendJsboxForm,
    }
