from django import forms
from go.contacts import models


widebox = forms.TextInput(attrs={'class': 'txtbox widebox'})
wideselect = forms.SelectMultiple(attrs={'class': 'mult-select'})


class ContactForm(forms.ModelForm):
    class Meta:
        model = models.Contact
        fields = (
            'name',
            'surname',
            'email_address',
            'msisdn',
            'dob',
            'groups',
            'twitter_handle',
            'facebook_id',
            'bbm_pin',
            'gtalk_id',
        )
        widgets = {
            'name': widebox,
            'surname': widebox,
            'email_address': widebox,
            'msisdn': widebox,
            'dob': widebox,
            'twitter_handle': widebox,
            'facebook_id': widebox,
            'bbm_pin': widebox,
            'gtalk_id': widebox,
            'groups': wideselect,
        }


class NewContactGroupForm(forms.ModelForm):
    class Meta:
        model = models.ContactGroup
        fields = (
            'name',
        )
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'txtbox'
            })
        }


class UploadContactsForm(forms.Form):
    file = forms.FileField(widget=forms.FileInput(attrs={
        'class': 'txtbox'
    }))


class SelectContactGroupForm(forms.Form):
    contact_group = forms.ModelChoiceField(
        queryset=models.ContactGroup.objects.all())
