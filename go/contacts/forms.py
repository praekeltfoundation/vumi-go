from django import forms
from bootstrap.forms import BootstrapForm


widebox = forms.TextInput(attrs={'class': 'txtbox widebox'})
wideselect = forms.SelectMultiple(attrs={'class': 'mult-select'})


class ContactForm(forms.Form):
    name = forms.CharField(widget=widebox)
    surname = forms.CharField(widget=widebox)

    email_address = forms.CharField(widget=widebox, required=False)
    msisdn = forms.CharField(label='Contact number',
        widget=widebox, required=False)
    twitter_handle = forms.CharField(widget=widebox, required=False)
    facebook_id = forms.CharField(widget=widebox, required=False)
    bbm_pin = forms.CharField(widget=widebox, required=False)
    gtalk_id = forms.CharField(widget=widebox, required=False)
    dob = forms.DateTimeField(widget=widebox, required=False)

    # groups is a special magic field that we add in __init__
    def __init__(self, *args, **kw):
        groups = kw.pop('groups')
        super(ContactForm, self).__init__(*args, **kw)
        self.fields['groups'] = forms.MultipleChoiceField(
            widget=wideselect, choices=[(g.key, g.name) for g in groups])


class NewContactGroupForm(BootstrapForm):
    name = forms.CharField(label="Create a new Group")


class UploadContactsForm(BootstrapForm):
    file = forms.FileField(label="File with Contact data",
        help_text="This can either be a double-quoted CSV file or an "
                    "Excel spreadsheet")


class SelectContactGroupForm(BootstrapForm):
    # contact_group is a special magic field that we add in __init__

    def __init__(self, *args, **kw):
        groups = kw.pop('groups')
        super(SelectContactGroupForm, self).__init__(*args, **kw)
        self.fields['contact_group'] = forms.ChoiceField(
            label="Select group to store contacts in.",
            help_text="Or provide a name for a new group below.",
            choices=[(g.key, g.name) for g in groups])
