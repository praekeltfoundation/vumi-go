from django import forms

from go.conversation.view_definition import (
    ConversationViewDefinitionBase, EditConversationView)

from go.apps.http_api_nostream.definition import DEFAULT_METRIC_STORE


class TokenForm(forms.Form):
    api_tokens = forms.CharField(
        label='API token',
        help_text='The access token for this HTTP Conversation.',
        required=True)
    ignore_messages = forms.BooleanField(
        label='Ignore messages instead of forwarding them.',
        required=False)
    push_message_url = forms.CharField(
        label='Push message URL',
        help_text='The URL to forward messages to via HTTP POST.',
        required=False)
    ignore_events = forms.BooleanField(
        label='Ignore events instead of forwarding them.',
        required=False)
    push_event_url = forms.CharField(
        label='Push event URL',
        help_text='The URL to forward events to via HTTP POST.',
        required=False)
    metric_store = forms.CharField(
        help_text='Which store to publish metrics to.',
        required=False)
    content_length_limit = forms.IntegerField(
        help_text=('Optional content length limit. If set, messages with'
                   ' content longer than this will be rejected.'),
        required=False)

    def clean(self):
        cleaned_data = super(TokenForm, self).clean()

        if not cleaned_data['ignore_messages']:
            if not cleaned_data['push_message_url']:
                self._errors['push_message_url'] = self.error_class([
                    u'This field is required unless messages are ignored.'])
                del cleaned_data['push_message_url']

        if not cleaned_data['ignore_events']:
            if not cleaned_data['push_event_url']:
                self._errors['push_event_url'] = self.error_class([
                    u'This field is required unless events are ignored.'])
                del cleaned_data['push_event_url']

        return cleaned_data

    @staticmethod
    def initial_from_config(data):
        data.setdefault('api_tokens', [])
        return {
            'api_tokens': (data['api_tokens'][0]
                           if data['api_tokens'] else None),
            'push_message_url': data.get('push_message_url', None),
            'push_event_url': data.get('push_event_url', None),
            'metric_store': data.get('metric_store', DEFAULT_METRIC_STORE),
            'ignore_events': data.get('ignore_events', False),
            'ignore_messages': data.get('ignore_messages', False),
            'content_length_limit': data.get('content_length_limit', None),
        }

    def to_config(self):
        data = self.cleaned_data
        return {
            'api_tokens': [data['api_tokens']],
            'push_message_url': data['push_message_url'] or None,
            'push_event_url': data['push_event_url'] or None,
            'metric_store': data.get('metric_store') or DEFAULT_METRIC_STORE,
            'ignore_events': data.get('ignore_events', False),
            'ignore_messages': data.get('ignore_messages', False),
            'content_length_limit': data.get('content_length_limit', None),
        }


class EditHttpApiNoStreamView(EditConversationView):
    edit_forms = (
        ('http_api_nostream', TokenForm),
    )
    help_template = 'http_api_nostream/edit_help.html'


class ConversationViewDefinition(ConversationViewDefinitionBase):
    edit_view = EditHttpApiNoStreamView
