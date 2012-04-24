from django import forms
from go.conversation import models


class ConversationForm(forms.ModelForm):
    subject = forms.CharField(required=True, widget=forms.TextInput(attrs={
        'class': 'input required'}))
    message = forms.CharField(required=True, widget=forms.Textarea(attrs={
        'class': 'input-xlarge required valid', 'id': 'conv-message'}))
    start_date = forms.DateField(required=False, widget=forms.TextInput(
        attrs={'id': 'datepicker', 'class': 'txtbox txtbox-date'}))
    start_time = forms.TimeField(required=False, widget=forms.TextInput(
        attrs={'id': 'timepicker_1', 'class': 'txtbox txtbox-date'}))
    delivery_class = forms.CharField(required=True, widget=forms.RadioSelect(
        attrs={'class': 'deliver-class-radio'},
        choices=models.get_delivery_class_names()))
    delivery_tag_pool = forms.CharField(required=True, widget=forms.Select(
        attrs={'class': 'input-medium'},
        choices=models.get_tag_pool_names()))

    class Meta:
        model = models.Conversation
        fields = (
            'subject',
            'message',
            'start_date',
            'start_time',
            'delivery_class',
            'delivery_tag_pool',
        )


class SelectDeliveryClassForm(forms.Form):
    delivery_class = forms.ChoiceField(
                        choices=models.get_combined_delivery_classes())
