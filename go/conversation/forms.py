from django import forms
from go.conversation import models
from go.contacts.models import ContactGroup


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
        attrs={'class': 'delivery-class-radio'},
        choices=[(dc,dc) for dc in models.get_delivery_class_names()]))
    delivery_tag_pool = forms.CharField(required=True, widget=forms.Select(
        attrs={'class': 'input-medium'},
        choices=[(tpn, tpn) for tpn in models.get_tag_pool_names()]))

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

class BulkSendConversationForm(ConversationForm):
    """Same as the ConversationForm with the only difference being that
    this only only allows for delivery classes that allow for server
    initiated conversations."""
    delivery_class = forms.CharField(required=True, widget=forms.RadioSelect(
        attrs={'class': 'delivery-class-radio'},
        choices=[(dc,dc) for dc
                    in models.get_server_init_delivery_class_names()]))
    delivery_tag_pool = forms.CharField(required=True, widget=forms.Select(
        attrs={'class': 'input-medium'},
        choices=[(tpn, tpn) for tpn
                        in models.get_server_init_tag_pool_names()]))

class ConversationGroupForm(forms.Form):
    groups = forms.ModelMultipleChoiceField(
            queryset=ContactGroup.objects.all(),
            widget=forms.CheckboxSelectMultiple)

class ConversationSearchForm(forms.Form):
    query = forms.CharField(required=False, widget=forms.TextInput(attrs={
        'class': 'input-xlarge',
        'id': 'search-filter-input',
        'placeholder': 'Search conversations...',
        }))
    conversation_type = forms.ChoiceField(required=False,
        choices=([('', 'Type ...')] + models.CONVERSATION_TYPES),
        widget=forms.Select(attrs={'class': 'input-small'}))
    conversation_status = forms.ChoiceField(required=False,
        choices=[
            ('', 'Status ...'),
            ('running', 'Running'),
            ('finished', 'Finished'),
            ('draft', 'Draft'),
        ],
        widget=forms.Select(attrs={'class': 'input-small'}))

class SelectDeliveryClassForm(forms.Form):
    delivery_class = forms.ChoiceField(
                        choices=models.get_combined_delivery_classes())
