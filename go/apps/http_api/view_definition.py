from go.conversation.view_definition import (
    ConversationViewDefinitionBase, EditConversationView)

from go.apps.http_api_nostream.view_definition import (
    TokenForm)


class EditHttpApiView(EditConversationView):
    edit_forms = (
        ('http_api', TokenForm),
    )


class ConversationViewDefinition(ConversationViewDefinitionBase):
    edit_view = EditHttpApiView
