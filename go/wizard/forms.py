from django import forms
from django.forms.widgets import RadioSelect


class Wizard1CreateForm(forms.Form):
    CHANNEL_CHOICES = (
        ('new', 'Setup a new channel'),
        ('existing', 'Use a keyword to route messages over an existing \
            channel'),
    )

    channel_kind = forms.ChoiceField(label="Channels", choices=CHANNEL_CHOICES,
                                     required=False, widget=RadioSelect)
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
