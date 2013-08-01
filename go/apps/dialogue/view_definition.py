from django.http import HttpResponse
from bootstrap.forms import BootstrapForm

from go.api.go_api import client
from go.api.go_api.client import GoApiError
from go.conversation.view_definition import (
    ConversationViewDefinitionBase, ConversationTemplateView)


class DialogueEditView(ConversationTemplateView):
    """This app is a unique and special snowflake, so it gets special views.
    """
    view_name = 'edit'
    path_suffix = 'edit/'
    template_base = 'dialogue'

    def get(self, request, conversation):
        r = client.rpc(
            request.session.session_key, 'conversation_action',
            [request.user_api.user_account_key,
             conversation.key, 'get_poll'])

        if r.status_code != 200:
            raise GoApiError(
                "Failed to load routing table from Go API:"
                " (%r) %r." % (r.status_code, r.text))

        model_data = {'campaign_id': request.user_api.user_account_key}
        model_data.update(r.json['result']['poll'])

        return self.render_to_response({
            'conversation': conversation,
            'session_id': request.session.session_key,
            'model_data': model_data,
        })


class UserDataView(ConversationTemplateView):
    view_name = 'user_data'
    path_suffix = 'users.csv'

    def get(self, request, conversation):
        # TODO: write new CSV data export
        csv_data = "TODO: write data export."
        return HttpResponse(csv_data, content_type='application/csv')


class SendDialogueForm(BootstrapForm):
    # TODO: Something better than this?
    pass


class ConversationViewDefinition(ConversationViewDefinitionBase):
    edit_view = DialogueEditView

    extra_views = (
        UserDataView,
    )

    action_forms = {
        'send_dialogue': SendDialogueForm,
    }
