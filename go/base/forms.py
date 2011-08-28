from django import forms
from go.base import models

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
        queryset=models.ContactGroup.objects.all(), empty_label=None)