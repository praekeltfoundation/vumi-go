from django import forms


widebox = forms.TextInput(attrs={'class': 'txtbox widebox'})
wideselect = forms.SelectMultiple(attrs={'class': 'mult-select'})


class ContactForm(forms.Form):
    name = forms.CharField(widget=widebox)
    surname = forms.CharField(widget=widebox)

    email_address = forms.CharField(widget=widebox, required=False)
    msisdn = forms.CharField(widget=widebox, required=False)
    twitter_handle = forms.CharField(widget=widebox, required=False)
    facebook_id = forms.CharField(widget=widebox, required=False)
    bbm_pin = forms.CharField(widget=widebox, required=False)
    gtalk_id = forms.CharField(widget=widebox, required=False)
    # dob = forms.CharField(widget=widebox, required=False)

    # groups is a special magic field that we add in __init__

    def __init__(self, *args, **kw):
        group_names = kw.pop('group_names')
        super(ContactForm, self).__init__(*args, **kw)
        self.fields['groups'] = forms.MultipleChoiceField(
            widget=wideselect, choices=[(n, n) for n in group_names])


class NewContactGroupForm(forms.Form):
    name = forms.CharField(widget=forms.TextInput(attrs={'class': 'txtbox'}))


class UploadContactsForm(forms.Form):
    file = forms.FileField(widget=forms.FileInput(attrs={
        'class': 'txtbox'
    }))


class SelectContactGroupForm(forms.Form):
    # contact_group is a special magic field that we add in __init__

    def __init__(self, *args, **kw):
        group_names = kw.pop('group_names')
        super(SelectContactGroupForm, self).__init__(*args, **kw)
        self.fields['contact_group'] = forms.ChoiceField(
            choices=[(n, n) for n in group_names])
