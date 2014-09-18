from django import forms

from go.conversation.view_definition import (
    ConversationViewDefinitionBase, EditConversationView)


class ConfigForm(forms.Form):
    api_url = forms.CharField(
        help_text="The mediawiki API URL to use.", required=False)
    include_url_in_sms = forms.BooleanField(
        help_text="Include URL in the first SMS.", required=False)
    mobi_url_host = forms.CharField(
        help_text="The replacement URL base to use in the first SMS.",
        required=False)
    shortening_api_url = forms.CharField(
        help_text="The Praekelt URL Shortening Service API URL to use.",
        required=False)
    transliterate_unicode = forms.BooleanField(
        help_text=(
            "Transliterate any non-ASCII characters. This is useful for"
            " channels that don't fully support unicode, but problematic"
            " for languages that use non-latin characters."),
        required=False)

    @staticmethod
    def initial_from_config(data):
        return {
            'api_url': data.get('api_url', None),
            'include_url_in_sms': data.get('include_url_in_sms', False),
            'mobi_url_host': data.get('mobi_url_host', None),
            'shortening_api_url': data.get('shortening_api_url', None),
            'transliterate_unicode': data.get('transliterate_unicode', False),
        }

    def to_config(self):
        data = self.cleaned_data
        config_dict = {
            'include_url_in_sms': data['include_url_in_sms'],
            'transliterate_unicode': data['transliterate_unicode'],
        }
        if data['api_url']:
            config_dict['api_url'] = data['api_url']
        if data['mobi_url_host']:
            config_dict['mobi_url_host'] = data['mobi_url_host']
        if data['shortening_api_url']:
            config_dict['shortening_api_url'] = data['shortening_api_url']
        return config_dict


class EditWikipediaView(EditConversationView):
    edit_forms = (
        (None, ConfigForm),
    )


class ConversationViewDefinition(ConversationViewDefinitionBase):
    edit_view = EditWikipediaView
