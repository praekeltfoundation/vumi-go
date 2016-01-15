import json

from django import forms

from go.api.go_api import client
from go.api.go_api.client import GoApiError
from go.conversation.view_definition import (
    ConversationViewDefinitionBase, ConversationTemplateView)
from go.vumitools.contact.models import (
    DELIVERY_CLASSES, DEFAULT_DELIVERY_CLASS)


class DialogueEditView(ConversationTemplateView):
    """This app is a unique and special snowflake, so it gets special views.
    """
    view_name = 'edit'
    path_suffix = 'edit/'
    template_base = 'dialogue'

    def get(self, request, conversation):
        r = client.rpc(
            request.session.session_key, 'conversation.dialogue.get_poll',
            [request.user_api.user_account_key,
             conversation.key])

        if r.status_code != 200:
            raise GoApiError(
                "Failed to load dialogue from Go API:"
                " (%r) %r." % (r.status_code, r.text))

        contact_store = conversation.user_api.contact_store
        groups = contact_store.list_static_groups()

        delivery_classes = [{
            'name': d_name,
            'label': d['label']
        } for d_name, d in DELIVERY_CLASSES.iteritems()]

        model_data = r.json()['result']['poll']
        model_data.update({
            'campaign_id': request.user_api.user_account_key,
            'conversation_key': conversation.key,
            'groups': [g.get_data() for g in groups],
            'channel_types': delivery_classes,
            'urls': {
                'show': self.get_view_url(
                    'show',
                    conversation_key=conversation.key)
            }
        })

        metadata = model_data.get('poll_metadata', {})
        delivery_class = metadata.get('delivery_class', DEFAULT_DELIVERY_CLASS)

        return self.render_to_response({
            'current_delivery_class': delivery_class,
            'delivery_classes': delivery_classes,
            'conversation': conversation,
            'session_id': request.session.session_key,
            'model_data': json.dumps(model_data),
        })


class SendDialogueForm(forms.Form):
    scheduled_datetime = forms.DateTimeField(
        widget=forms.HiddenInput(), required=False)


class ConversationViewDefinition(ConversationViewDefinitionBase):
    edit_view = DialogueEditView

    action_forms = {
        'send_jsbox': SendDialogueForm,
    }
