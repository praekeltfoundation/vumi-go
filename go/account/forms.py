from django import forms
from registration.forms import RegistrationFormUniqueEmail

from bootstrap.forms import BootstrapMixin, BootstrapForm, Fieldset

from vumi.utils import normalize_msisdn


class AccountForm(BootstrapForm):

    def __init__(self, user, *args, **kwargs):
        super(AccountForm, self).__init__(*args, **kwargs)
        self.user = user

    name = forms.CharField(required=True)
    surname = forms.CharField(required=True)
    email_address = forms.EmailField(required=True, widget=forms.TextInput(
        attrs={'autocomplete': 'off'}))
    msisdn = forms.CharField(label='Your mobile phone number', required=False)
    confirm_start_conversation = forms.BooleanField(
        label='SMS to confirm starting of a conversation', required=False)
    existing_password = forms.CharField(
        label='Your existing password',
        widget=forms.PasswordInput(attrs={
            'autocomplete': 'off',
            }),
        required=True)
    new_password = forms.CharField(
        label='Type in a password if you want a new one.',
        widget=forms.PasswordInput(attrs={
            'autocomplete': 'off',
        }),
        required=False)

    class Meta:
        layout = (
            Fieldset('Account Information',
                "name",
                "surname",
                "email_address",
                "msisdn",
                "confirm_start_conversation",
                "new_password",),
            Fieldset('Verify your password',
                'existing_password'))

    def clean(self):
        """
        Checks whether the existing password matches the known password
        for this user because we only want to update these details
        if the user can actually supply their original password.
        """
        cleaned_data = self.cleaned_data
        password = cleaned_data.get('existing_password')
        if not self.user.check_password(password):
            self._errors['existing_password'] = ['Invalid password provided']
        return cleaned_data

    def clean_msisdn(self):
        """
        Make a best effort guess at determining whether this msisdn
        is a valid msisdn
        """
        msisdn = self.cleaned_data['msisdn'].lstrip('+')
        if not msisdn:
            return ''

        if not (len(msisdn) > 5 and
                all(c.isdigit() for c in msisdn)):
            raise forms.ValidationError('Please provide a valid phone number.')
        return normalize_msisdn(msisdn)

    def clean_confirm_start_conversation(self):
        confirm_start_conversation = self.cleaned_data[
                                                'confirm_start_conversation']
        msisdn = self.cleaned_data.get('msisdn')
        if confirm_start_conversation and not msisdn:
            self._errors['msisdn'] = ['Please provide a valid phone number.']
        return confirm_start_conversation


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
