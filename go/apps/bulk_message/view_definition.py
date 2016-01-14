from django import forms

from go.conversation.view_definition import (
    ConversationActionView, ConversationViewDefinitionBase)
from go.base.widgets import BulkMessageWidget
from go.vumitools.contact.models import DELIVERY_CLASSES


DEFAULT_BULK_SEND_DELIVERY_CLASS = 'sms'


class MessageForm(forms.Form):
    message = forms.CharField(widget=BulkMessageWidget)
    delivery_class = forms.ChoiceField(
        label="Channel type",
        required=True,
        initial=DEFAULT_BULK_SEND_DELIVERY_CLASS,
        choices=[(d_name, d['label']) for d_name, d
                 in DELIVERY_CLASSES.iteritems()])
    dedupe = forms.BooleanField(required=False)
    scheduled_datetime = forms.DateTimeField(
        widget=forms.HiddenInput(), required=False)


class BulkSendView(ConversationActionView):
    view_name = 'bulk_send'


class ConversationViewDefinition(ConversationViewDefinitionBase):
    action_forms = {
        'bulk_send': MessageForm,
    }

    action_views = {
        'bulk_send': BulkSendView,
    }
