from django import forms
from django.forms import widgets

from bootstrap.forms import BootstrapForm

from go.conversation.base import ConversationViews


class JavascriptField(forms.CharField):
    widget = widgets.Textarea


class JsboxForm(BootstrapForm):
    javascript = JavascriptField()
    source_url = forms.CharField(required=False)
    update_from_source = forms.BooleanField(required=False)

    def _load_from_url(self, url):
        # TODO: implement
        return "TODO: source from url (%s)" % url

    def to_metadata(self):
        metadata = self.cleaned_data.copy()
        if metadata['update_from_source']:
            metadata['javascript'] = self._load_from_url(
                metadata['source_url'])
        del metadata['update_from_source']
        return metadata


class JsboxConversationViews(ConversationViews):
    conversation_type = u'jsbox'
    conversation_display_name = u'Javascript App'
    conversation_initiator = None
    edit_conversation_forms = (
        ('jsbox', JsboxForm),
        )
