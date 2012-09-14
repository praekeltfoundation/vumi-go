from bootstrap.forms import BootstrapForm
from django import forms


class ContactForm(BootstrapForm):
    name = forms.CharField()
    surname = forms.CharField()

    email_address = forms.CharField(required=False)
    msisdn = forms.CharField(label='Contact number', required=False)
    twitter_handle = forms.CharField(required=False)
    facebook_id = forms.CharField(required=False)
    bbm_pin = forms.CharField(required=False)
    gtalk_id = forms.CharField(required=False)
    dob = forms.DateTimeField(required=False)

    # groups is a special magic field that we add in __init__
    def __init__(self, *args, **kw):
        groups = kw.pop('groups')
        super(ContactForm, self).__init__(*args, **kw)
        self.fields['groups'] = forms.MultipleChoiceField(
            choices=[(g.key, g.name) for g in groups])


class ContactGroupForm(BootstrapForm):
    name = forms.CharField(label="Create a Group")

class SmartGroupForm(BootstrapForm):
    name = forms.CharField()
    query = forms.CharField()

class UploadContactsForm(BootstrapForm):
    file = forms.FileField(label="File with Contact data",
        help_text="This can either be a double-quoted UTF-8 encoded CSV file "
                    "or an Excel spreadsheet")


class SelectContactGroupForm(BootstrapForm):
    # contact_group is a special magic field that we add in __init__

    def __init__(self, *args, **kw):
        groups = kw.pop('groups')
        super(SelectContactGroupForm, self).__init__(*args, **kw)
        self.fields['contact_group'] = forms.ChoiceField(
            label="Select group to store contacts in.",
            help_text="Or provide a name for a new group below.",
            choices=[(g.key, g.name) for g in groups])
