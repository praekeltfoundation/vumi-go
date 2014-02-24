from django import forms

from go.conversation.view_definition import (
    ConversationViewDefinitionBase, EditConversationView)


class ConfigForm(forms.Form):
    api_url = forms.CharField(
        help_text='The mediawiki API URL to use.', required=False)

    @staticmethod
    def initial_from_config(data):
        return {
            'api_url': data.get('api_url', None),
        }

    def to_config(self):
        data = self.cleaned_data
        config_dict = {}
        if data['api_url']:
            config_dict['api_url'] = data['api_url']
        return config_dict


class EditWikipediaView(EditConversationView):
    edit_forms = (
        (None, ConfigForm),
    )


class ConversationViewDefinition(ConversationViewDefinitionBase):
    edit_view = EditWikipediaView
