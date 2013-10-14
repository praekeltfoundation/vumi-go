from django import forms

from go.conversation.view_definition import ConversationViewDefinitionBase
from go.base.widgets import BulkMessageWidget


class MessageForm(forms.Form):
    message = forms.CharField(widget=BulkMessageWidget)
    dedupe = forms.BooleanField(required=False)


class ConversationViewDefinition(ConversationViewDefinitionBase):
    action_forms = {
        'bulk_send': MessageForm,
    }
