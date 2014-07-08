from django import forms

from go.conversation.view_definition import (
    ConversationViewDefinitionBase, EditConversationView)

from go.apps.http_api_nostream.view_definition import (
    TokenForm)


class MyTokenForm(TokenForm):
    # Inherit all fields from nostream version, but replace the push URL fields
    # with optional versions.
    push_message_url = forms.CharField(
        help_text=('The URL to forward messages to via HTTP POST.'
                   ' (If unset, messages will be streamed to clients.)'),
        required=False)
    push_event_url = forms.CharField(
        help_text=('The URL to forward events to via HTTP POST.'
                   ' (If unset, events will be streamed to clients.)'),
        required=False)


class EditHttpApiView(EditConversationView):
    edit_forms = (
        ('http_api', MyTokenForm),
    )


class ConversationViewDefinition(ConversationViewDefinitionBase):
    edit_view = EditHttpApiView
