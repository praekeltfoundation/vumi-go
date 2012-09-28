from django import forms
from registration.forms import RegistrationFormUniqueEmail

from bootstrap.forms import BootstrapMixin, BootstrapForm


class AccountForm(BootstrapForm):
    name = forms.CharField(required=True)
    surname = forms.CharField(required=True)
    email_address = forms.EmailField(required=True, widget=forms.TextInput(
        attrs={'autocomplete': 'off'}))
    password = forms.CharField(
        label='Type in a password if you want a new one.',
        widget=forms.PasswordInput(attrs={
            'autocomplete': 'off',
        }),
        required=False)


class RegistrationForm(BootstrapMixin, RegistrationFormUniqueEmail):
    def __init__(self, *args, **kwargs):
        super(RegistrationForm, self).__init__(*args, **kwargs)
        del self.fields['username']

    def clean(self):
        if not self.errors:
            self.cleaned_data['username'] = self.cleaned_data['email']
        return self.cleaned_data


class EmailForm(BootstrapForm):
    subject = forms.CharField()
    message = forms.CharField(widget=forms.Textarea)
