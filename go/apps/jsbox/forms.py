import requests

from django import forms
from django.forms import widgets
from django.forms.formsets import BaseFormSet

from bootstrap.forms import BootstrapForm


def possibly_load_from_url(url, default_value, update):
    """Possibly load a value from a URL.

    Returns the body of the response from the URL if update is True
    and the URL is non-empty and a request to the URL returns
    successfully. Otherwise returns the default value.
    """
    if update and url:
        response = requests.get(url)
        if response.ok:
            return response.text
    return default_value


class JavascriptField(forms.CharField):
    widget = widgets.Textarea


class JsboxForm(BootstrapForm):
    javascript = JavascriptField(required=False)
    source_url = forms.URLField(required=False)
    update_from_source = forms.BooleanField(required=False)

    @staticmethod
    def initial_from_metadata(metadata):
        return metadata

    def to_metadata(self):
        javascript = possibly_load_from_url(
            self.cleaned_data['source_url'],
            self.cleaned_data['javascript'],
            self.cleaned_data['update_from_source'],
        )
        return {
            'javascript': javascript,
            'source_url': self.cleaned_data['source_url'],
        }


class ConfigValueField(forms.CharField):
    widget = widgets.Textarea


class JsboxAppConfigForm(BootstrapForm):
    key = forms.CharField()
    value = ConfigValueField(required=False)
    source_url = forms.URLField(required=False)
    update_from_source = forms.BooleanField(required=False)

    @staticmethod
    def initial_from_metadata(metadata):
        return metadata

    def to_metadata(self):
        value = possibly_load_from_url(
            self.cleaned_data['source_url'],
            self.cleaned_data['value'],
            self.cleaned_data['update_from_source'],
        )
        return {
            'key': self.cleaned_data['key'],
            'value': value,
            'source_url': self.cleaned_data['source_url'],
        }


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
        return metadata

    @classmethod
    def initial_from_metadata(cls, metadata):
        initials = []
        for key in sorted(metadata):
            submeta = metadata[key].copy()
            submeta['key'] = key
            if hasattr(cls.form, 'initial_from_metadata'):
                submeta = getattr(cls.form, 'initial_from_metadata')(submeta)
            initials.append(submeta)
        return initials
