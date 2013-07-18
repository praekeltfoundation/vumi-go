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
