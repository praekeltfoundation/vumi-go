from django import forms

class QuestionForm(forms.Form):
    copy = forms.CharField(widget=forms.Textarea, required=True)
    label = forms.CharField(widget=forms.TextInput, required=True)
    valid_responses = forms.CharField(widget=forms.Textarea, required=False)
    check_field = forms.CharField(widget=forms.TextInput, required=False)
    check_value = forms.CharField(widget=forms.TextInput, required=False)
