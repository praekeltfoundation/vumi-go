from django import forms
from django.forms.formsets import BaseFormSet

from bootstrap.forms import BootstrapForm
from go.base.widgets import CodeField, SourceUrlField


class JsboxForm(BootstrapForm):
    javascript = CodeField(required=False)
    source_url = SourceUrlField(dest=javascript, required=False)

    @staticmethod
    def initial_from_metadata(metadata):
        return metadata

    def to_metadata(self):
        return {
            'javascript': self.cleaned_data['javascript'],
            'source_url': self.cleaned_data['source_url'],
        }


class JsboxAppConfigForm(BootstrapForm):
    key = forms.CharField()
    value = CodeField(required=False)
    source_url = SourceUrlField(dest=value, required=False)

    @staticmethod
    def initial_from_metadata(metadata):
        return metadata

    def to_metadata(self):
        return {
            'key': self.cleaned_data['key'],
            'value': self.cleaned_data['value'],
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
