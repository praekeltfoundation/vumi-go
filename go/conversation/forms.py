from django import forms
from go.conversation import models


class ConversationForm(forms.ModelForm):
    subject = forms.CharField(required=True, widget=forms.TextInput(attrs={
        'class': 'txtbox required'}))
    message = forms.CharField(required=True, widget=forms.Textarea(attrs={
        'class': 'required', 'id': 'conv-message'}))
    start_date = forms.DateField(required=False, widget=forms.TextInput(
        attrs={'id': 'datepicker', 'class': 'txtbox txtbox-date'}))
    start_time = forms.TimeField(required=False, widget=forms.TextInput(
        attrs={'id': 'timepicker_1', 'class': 'txtbox txtbox-date'}))

    class Meta:
        model = models.Conversation
        fields = (
            'subject',
            'message',
            'start_date',
            'start_time',
        )


class SelectDeliveryClassForm(forms.Form):
    delivery_class = forms.ChoiceField(choices=[
            ('sms', 'SMS'),
            ('gtalk', 'Google Talk'),
            ])
