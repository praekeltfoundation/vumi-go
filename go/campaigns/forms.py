from django import forms


class CampaignForm(forms.Form):

    TYPE_CHOICES = (
            ('', 'Select campaign type'),
            ('B', 'Bulk Message'),
            ('C', 'Conversation'),
        )

    name = forms.CharField(label="Campaign name", max_length=100)
    type = forms.ChoiceField(label="Which kind of campaign would you like?", 
                             widget=forms.Select(), choices=TYPE_CHOICES)
