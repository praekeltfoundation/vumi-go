import requests

from django import forms
from django.forms import widgets
from django.forms.formsets import BaseFormSet

from bootstrap.forms import BootstrapForm


class JavascriptField(forms.CharField):
    widget = widgets.Textarea


class JsboxForm(BootstrapForm):
    javascript = JavascriptField(required=False)
    source_url = forms.URLField(required=False)
    update_from_source = forms.BooleanField(required=False)

    def _update_from_source(self, url):
        response = requests.get(url)
        if response.ok:
            return response.text

    def to_metadata(self):
        metadata = self.cleaned_data.copy()
        if metadata['update_from_source']:
            source = self._update_from_source(metadata['source_url'])
            if source is not None:
                metadata['javascript'] = source
        del metadata['update_from_source']
        return metadata


class ConfigValueField(forms.CharField):
    widget = widgets.Textarea


class JsboxAppConfigForm(BootstrapForm):
    key = forms.CharField()
    value = ConfigValueField(required=False)
    source_url = forms.URLField(required=False)
    update_from_source = forms.BooleanField(required=False)

    def _update_from_source(self, url):
        response = requests.get(url)
        if response.ok:
            return response.text

    def to_metadata(self):
        metadata = self.cleaned_data.copy()
        if metadata['update_from_source']:
            source = self._update_from_source(metadata['source_url'])
            if source is not None:
                metadata['value'] = source
        del metadata['update_from_source']
        return metadata


class JsboxAppConfigFormset(BaseFormSet):
    form = JsboxAppConfigForm
    extra = 1
    can_order = False
    can_delete = True
    max_num = None

    def to_metadata(self):
        metadata = {}
        for form in self.forms:
            if not form.cleaned_data or form in self.deleted_forms:
                continue
            submeta = form.to_metadata()
            metadata[submeta['key']] = submeta
            del submeta['key']
            del submeta['DELETE']  # remove formset deletion marker
        return metadata

    @staticmethod
    def initial_from_metadata(metadata):
        initials = []
        for key in sorted(metadata):
            submeta = metadata[key].copy()
            submeta['key'] = key
            initials.append(submeta)
        return initials
