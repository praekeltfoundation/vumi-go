from django import forms
from django.forms.widgets import RadioSelect


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
