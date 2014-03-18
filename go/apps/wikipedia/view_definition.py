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

    @staticmethod
    def initial_from_config(data):
        return {
            'api_url': data.get('api_url', None),
            'include_url_in_sms': data.get('include_url_in_sms', False),
            'mobi_url_host': data.get('mobi_url_host', None),
        }

    def to_config(self):
        data = self.cleaned_data
        config_dict = {
            'include_url_in_sms': data['include_url_in_sms'],
        }
        if data['api_url']:
            config_dict['api_url'] = data['api_url']
        if data['mobi_url_host']:
            config_dict['mobi_url_host'] = data['mobi_url_host']
        return config_dict


class EditWikipediaView(EditConversationView):
    edit_forms = (
        (None, ConfigForm),
    )


class ConversationViewDefinition(ConversationViewDefinitionBase):
    edit_view = EditWikipediaView
