from django.http import HttpResponse
from bootstrap.forms import BootstrapForm


from go.conversation.view_definition import (
    ConversationViewDefinitionBase, ConversationTemplateView)


class DialogueEditView(ConversationTemplateView):
    """This app is a unique and special snowflake, so it gets special views.
    """
    view_name = 'edit'
    path_suffix = 'edit/'
    template_base = 'dialogue'

    def get(self, request, conversation):
        # TODO Use api to get model data and bootstrap it to page load

        return self.render_to_response({
            'conversation': conversation
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
