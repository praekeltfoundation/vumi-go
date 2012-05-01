from django import forms


class EmailForm(forms.Form):
    subject = forms.CharField()
    message = forms.CharField(widget=forms.Textarea)
