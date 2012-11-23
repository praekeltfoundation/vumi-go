import requests

from django import forms
from django.forms import widgets

from bootstrap.forms import BootstrapForm


class JavascriptField(forms.CharField):
    widget = widgets.Textarea


class JsboxForm(BootstrapForm):
    javascript = JavascriptField(required=False)
    source_url = forms.URLField(required=False)
    update_from_source = forms.BooleanField(required=False)

    def _update_from_source(self, url):
        return requests.get(url)

    def to_metadata(self):
        metadata = self.cleaned_data.copy()
        if metadata['update_from_source']:
            metadata['javascript'] = self._update_from_source(
                metadata['source_url'])
        del metadata['update_from_source']
        return metadata
