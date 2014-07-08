from django import forms

from go.conversation.view_definition import (
    ConversationViewDefinitionBase, EditConversationView)

from go.apps.http_api_nostream.definition import DEFAULT_METRIC_STORE


class TokenForm(forms.Form):
    api_tokens = forms.CharField(
        help_text='The access token for this HTTP Conversation.',
        required=True)
    push_message_url = forms.CharField(
        help_text='The URL to forward messages to via HTTP POST.',
        required=True)
    push_event_url = forms.CharField(
        help_text=('The URL to forward events to via HTTP POST.'
                   ' (If unset, events will not be forwarded.)'),
        required=False)
    metric_store = forms.CharField(
        help_text='Which store to publish metrics to.',
        required=False)

    @staticmethod
    def initial_from_config(data):
        data.setdefault('api_tokens', [])
        return {
            'api_tokens': (data['api_tokens'][0]
                           if data['api_tokens'] else None),
            'push_message_url': data.get('push_message_url', None),
            'push_event_url': data.get('push_event_url', None),
            'metric_store': data.get('metric_store', DEFAULT_METRIC_STORE),
        }

    def to_config(self):
        data = self.cleaned_data
        return {
            'api_tokens': [data['api_tokens']],
            'push_message_url': data['push_message_url'] or None,
            'push_event_url': data['push_event_url'] or None,
            'metric_store': data.get('metric_store') or DEFAULT_METRIC_STORE,
        }


class EditHttpApiNoStreamView(EditConversationView):
    edit_forms = (
        ('http_api_nostream', TokenForm),
    )


class ConversationViewDefinition(ConversationViewDefinitionBase):
    edit_view = EditHttpApiNoStreamView
