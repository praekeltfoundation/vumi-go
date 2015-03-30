from django import forms

from go.conversation.view_definition import (
    ConversationViewDefinitionBase, EditConversationView)

from go.apps.http_api_nostream.definition import DEFAULT_METRIC_STORE


class TokenForm(forms.Form):
    # This doesn't subclass the http_api_nostream version because the configs
    # are sufficiently different that it would be problematic to do so.

    api_tokens = forms.CharField(
        help_text='The access token for this HTTP Conversation.',
        required=True)
    push_message_url = forms.CharField(
        help_text=('The URL to forward messages to via HTTP POST.'
                   ' (If unset, messages will be streamed to clients.)'),
        required=False)
    push_event_url = forms.CharField(
        help_text=('The URL to forward events to via HTTP POST.'
                   ' (If unset, events will be streamed to clients.)'),
        required=False)
    metric_store = forms.CharField(
        help_text='Which store to publish metrics to.',
        required=False)
    content_length_limit = forms.IntegerField(
        help_text=('Optional content length limit. If set, messages with'
                   ' content longer than this will be rejected.'),
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
            'content_length_limit': data.get('content_length_limit', None),
        }

    def to_config(self):
        data = self.cleaned_data
        return {
            'api_tokens': [data['api_tokens']],
            'push_message_url': data['push_message_url'] or None,
            'push_event_url': data['push_event_url'] or None,
            'metric_store': data.get('metric_store') or DEFAULT_METRIC_STORE,
            'content_length_limit': data.get('content_length_limit', None),
            # The worker code checks these, but we don't provide config UI for
            # them. They should always be False.
            'ignore_events': False,
            'ignore_messages': False,
        }


class EditHttpApiView(EditConversationView):
    edit_forms = (
        ('http_api', TokenForm),
    )


class ConversationViewDefinition(ConversationViewDefinitionBase):
    edit_view = EditHttpApiView
