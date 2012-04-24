from django import forms
from vxpolls.content import fields

class QuestionForm(forms.Form):
    copy = forms.CharField(widget=forms.Textarea)
    label = forms.CharField(widget=forms.TextInput)
    valid_responses = forms.CharField(widget=forms.Textarea)
    checks = fields.CheckField(
        label='Only ask if',
        help_text='Skip this question unless the value of the'\
                    ' given label matches the answer given.',
        required=False)