from django import forms
from django.forms.widgets import RadioSelect


class CampaignGeneralForm(forms.Form):

    KIND_CHOICES = (
        ('bulk_message', 'Bulk Message'),
        ('survey', 'Dialogue'),
    )
    CHANNEL_CHOICES = (
        ('new', 'Setup a new channel'),
        ('existing', 'Use a keyword to route messages over an existing \
            channel'),
    )

    name = forms.CharField(label="Conversation name", max_length=100)
    kind = forms.ChoiceField(
        label="Which kind of conversation would you like?",
        choices=KIND_CHOICES
    )
    channel = forms.ChoiceField(label="Channels", choices=CHANNEL_CHOICES,
                                required=False, widget=RadioSelect)


class CampaignConfigurationForm(forms.Form):

    COUNTRY_CHOICES = (
        ('.za', 'South Africa'),
        ('.ke', 'Kenya'),
    )

    CHANNEL_CHOICES = (
        ('ussd', 'USSD'),
        ('sms', 'SMS'),
    )

    countries = forms.MultipleChoiceField(label="Select a destination",
                                          widget=forms.Select(),
                                          choices=COUNTRY_CHOICES)

    channels = forms.MultipleChoiceField(label="Select a channel",
                                         widget=forms.Select(),
                                         choices=CHANNEL_CHOICES)
    keyword = forms.CharField(label="Define a keyword", max_length=100)


class CampaignBulkMessageForm(forms.Form):
    message = forms.CharField(label="Bulk message text", widget=forms.Textarea)


class CampaignSurveryInitiateForm(forms.Form):
    INITIATE_CHOICES = (
        ('user', 'I will send users a notification message'),
        ('notification', 'Users will initiate it'),
    )
    initiate = forms.ChoiceField(label="", choices=INITIATE_CHOICES)
    expected_responses = forms.CharField(
        label="How many responses do you expect?")
