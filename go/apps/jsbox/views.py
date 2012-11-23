from django import forms
from django.forms import widgets

from bootstrap.forms import BootstrapForm

from go.conversation.base import ConversationViews


class JavascriptField(forms.CharField):
    widget = widgets.Textarea


class JsboxForm(BootstrapForm):
    javascript = JavascriptField()


class JsboxConversationViews(ConversationViews):
    conversation_type = u'jsbox'
    conversation_display_name = u'Javascript App'
    conversation_initiator = None
    edit_conversation_forms = (
        ('handlers', JsboxForm),
        )
