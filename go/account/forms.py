from django import forms


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


class EmailForm(forms.Form):
    subject = forms.CharField()
    message = forms.CharField(widget=forms.Textarea)
