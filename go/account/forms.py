from django import forms
from django.contrib.auth.models import User

from registration.forms import RegistrationFormUniqueEmail
from vumi.utils import normalize_msisdn

from go.base.models import UserProfile


class UserAccountForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        super(UserAccountForm, self).__init__(*args, **kwargs)
        self.fields['email'].required = True

    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'email')


class UserProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ('is_admin',)


class AccountForm(forms.Form):

    def __init__(self, user, *args, **kwargs):
        super(AccountForm, self).__init__(*args, **kwargs)
        self.user = user

    name = forms.CharField(required=True)
    surname = forms.CharField(required=True)
    email_address = forms.EmailField(label="Email", required=True,
        widget=forms.TextInput(attrs={'autocomplete': 'off'}))
    msisdn = forms.CharField(label='Mobile phone number', required=False)
    organisation = forms.CharField(label='Organisation name', required=False)
    country = forms.CharField(label='Country of residence', required=False)
    confirm_start_conversation = forms.BooleanField(
        label='Receive SMS to confirm start of campaign', required=False)
    email_summary = forms.ChoiceField(
        label='How often do you want to receive an account summary via email?',
        required=False, choices=(
            ('never', 'Never.'),
            ('daily', 'Once a day.'),
            ('weekly', 'Once a week.'),
        ))

    def clean_msisdn(self):
        """
        Make a best effort guess at determining whether this msisdn
        is a valid msisdn
        """
        if not self.cleaned_data['msisdn']:
            return ''

        msisdn = ''.join([char for char in self.cleaned_data['msisdn']
                            if char.isdigit()])
        if len(msisdn) <= 5:
            raise forms.ValidationError('Please provide a valid phone number.')
        return normalize_msisdn(msisdn)

    def clean_confirm_start_conversation(self):
        confirm_start_conversation = self.cleaned_data[
                                                'confirm_start_conversation']
        msisdn = self.cleaned_data.get('msisdn')
        if confirm_start_conversation and not msisdn:
            self._errors['msisdn'] = ['Please provide a valid phone number.']
        return confirm_start_conversation


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
