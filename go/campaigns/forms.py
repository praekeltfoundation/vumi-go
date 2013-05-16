from django import forms


class CampaignGeneralForm(forms.Form):

    TYPE_CHOICES = (
        ('', 'Select campaign type'),
        ('B', 'Bulk Message'),
        ('D', 'Dialogue'),
    )

    name = forms.CharField(label="Campaign name", max_length=100)
    type = forms.ChoiceField(label="Which kind of campaign would you like?",
                             widget=forms.Select(), choices=TYPE_CHOICES)


class CampaignConfigurationForm(forms.Form):

    COUNTRY_CHOICES = (
        ('.za', 'South Africa'),
    )

    CHANNEL_CHOICES = (
        ('ussd', 'USSD'),
    )

    # more than likely a many to many field, or something similair in the riak
    # world. Whom I kidding, this is probably just a modelform?
    countries = forms.MultipleChoiceField(label="Destinations",
                                          widget=forms.Select(),
                                          choices=COUNTRY_CHOICES)

    channels = forms.MultipleChoiceField(label="Channels",
                                         widget=forms.Select(),
                                         choices=CHANNEL_CHOICES)

    keyword = forms.CharField(label="Keyword", max_length=100)


class CampaignBulkMessageForm(forms.Form):
    message = forms.CharField(label="Bulk message text", widget=forms.Textarea)
