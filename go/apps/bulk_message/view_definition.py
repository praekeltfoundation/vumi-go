from django import forms

from go.conversation.view_definition import ConversationViewDefinitionBase
from go.base.widgets import BulkMessageWidget
from go.vumitools.contact.models import DELIVERY_CLASSES


DEFAULT_BULK_SEND_DELIVERY_CLASS = 'sms'


class MessageForm(forms.Form):
    message = forms.CharField(widget=BulkMessageWidget)
    delivery_class = forms.ChoiceField(
        required=True,
        initial=DEFAULT_BULK_SEND_DELIVERY_CLASS,
        choices=[(d_name, d['label']) for d_name, d
                 in DELIVERY_CLASSES.iteritems()])
    dedupe = forms.BooleanField(required=False)


class ConversationViewDefinition(ConversationViewDefinitionBase):
    action_forms = {
        'bulk_send': MessageForm,
    }
