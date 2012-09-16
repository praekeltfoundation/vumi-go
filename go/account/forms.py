from django import forms
from registration.forms import RegistrationFormUniqueEmail


class AccountForm(forms.Form):
    name = forms.CharField(required=True)
    surname = forms.CharField(required=True)
    email_address = forms.EmailField(required=True, widget=forms.TextInput(
        attrs={'class': 'input-xlarge required email', 'autocomplete': 'off'}))
    password = forms.CharField(
        label='Type in a password if you want a new one.',
        widget=forms.PasswordInput(attrs={
            'class': 'input-xlarge',
            'autocomplete': 'off',
        }),
        required=False)


class RegistrationForm(RegistrationFormUniqueEmail):
    def __init__(self, *args, **kwargs):
        super(RegistrationForm, self).__init__(*args, **kwargs)
        del self.fields['username']

    def clean(self):
        if not self.errors:
            self.cleaned_data['username'] = self.cleaned_data['email']
        return self.cleaned_data


class EmailForm(forms.Form):
    subject = forms.CharField()
    message = forms.CharField(widget=forms.Textarea)
