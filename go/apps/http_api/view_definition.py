from django import forms

from go.conversation.view_definition import (
    ConversationViewDefinitionBase, EditConversationView)


class TokenForm(forms.Form):
    api_tokens = forms.CharField(
            help_text='The access token for this HTTP Conversation.',
            required=True)
    push_message_url = forms.CharField(
        help_text='The URL to forward messages to via HTTP POST.',
        required=False)
    push_event_url = forms.CharField(
        help_text='The URL to forward events to via HTPT POST.',
        required=False)

    @staticmethod
    def initial_from_config(data):
        data.setdefault('api_tokens', [])
        return {
            'api_tokens': (data['api_tokens'][0]
                            if data['api_tokens'] else None),
            'push_message_url': data.get('push_message_url', None),
            'push_event_url': data.get('push_event_url', None),
        }

    def to_config(self):
        data = self.cleaned_data
        return {
            'api_tokens': [data['api_tokens']],
            'push_message_url': data['push_message_url'] or None,
            'push_event_url': data['push_event_url'] or None,
        }


class EditHttpApiView(EditConversationView):
    edit_forms = (
        ('http_api', TokenForm),
    )

class ConversationViewDefinition(ConversationViewDefinitionBase):
    edit_view = EditHttpApiView
