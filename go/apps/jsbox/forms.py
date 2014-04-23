from django import forms
from django.forms.formsets import BaseFormSet, formset_factory

from go.base.widgets import CodeField, SourceUrlField


SOURCE_URL_HELP_TEXT = (
    'HTTP Basic Authentication is supported. If using GitHub '
    'please use '
    '<a href="http://developer.github.com/v3/#authentication">'
    'OAuth2 access tokens'
    '</a>.')


class JsboxForm(forms.Form):
    javascript = CodeField(required=False)
    source_url = SourceUrlField(code_field='javascript',
                                help_text=SOURCE_URL_HELP_TEXT,
                                required=False)

    @staticmethod
    def initial_from_config(metadata):
        return metadata

    def to_config(self):
        return {
            'javascript': self.cleaned_data['javascript'],
            'source_url': self.cleaned_data['source_url'],
        }


class JsboxAppConfigForm(forms.Form):
    key = forms.CharField()
    value = CodeField(required=False)
    source_url = SourceUrlField(code_field='value',
                                help_text=None,
                                required=False)

    @staticmethod
    def initial_from_config(metadata):
        return metadata

    def to_config(self):
        return {
            'key': self.cleaned_data['key'],
            'value': self.cleaned_data['value'],
            'source_url': self.cleaned_data['source_url'],
        }


class BaseJsboxAppConfigFormset(BaseFormSet):

    def to_config(self):
        metadata = {}
        for form in self.forms:
            if not form.cleaned_data or form in self.deleted_forms:
                continue
            submeta = form.to_config()
            metadata[submeta['key']] = submeta
            del submeta['key']
        return metadata

    @classmethod
    def initial_from_config(cls, metadata):
        initials = []
        for key in sorted(metadata):
            submeta = metadata[key].copy()
            submeta['key'] = key
            if hasattr(cls.form, 'initial_from_config'):
                submeta = getattr(cls.form, 'initial_from_config')(submeta)
            initials.append(submeta)
        return initials

JsboxAppConfigFormset = formset_factory(
    JsboxAppConfigForm, can_delete=True, extra=1,
    formset=BaseJsboxAppConfigFormset)
