from django import forms
from django.forms import widgets

from bootstrap.forms import BootstrapForm

from go.conversation.base import ConversationViews


class JavascriptField(forms.CharField):
    widget = widgets.Textarea


class JsboxForm(BootstrapForm):
    javascript = JavascriptField()


JsboxFormSet = forms.formsets.formset_factory(
    JsboxForm, can_delete=True, extra=1)


class JsboxConversationViews(ConversationViews):
    conversation_type = u'jsbox'
    conversation_initiator = u'client'
    edit_conversation_forms = (
        ('handlers', JsboxFormSet),
        )
