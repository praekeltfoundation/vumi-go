from django import forms

from go.vumitools.conversation import (
    CONVERSATION_TYPES, get_tag_pool_names, get_delivery_class_names,
    get_server_init_delivery_class_names, get_server_init_tag_pool_names,
    get_combined_delivery_classes)


class ConversationForm(forms.Form):
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
        choices=[(dc, dc) for dc in get_delivery_class_names()]))
    delivery_tag_pool = forms.CharField(required=True, widget=forms.Select(
        attrs={'class': 'input-medium'},
        choices=[(tpn, tpn) for tpn in get_tag_pool_names()]))

    def delivery_class_widgets(self):
        # Backported hack from Django 1.4 to allow me to iterate
        # over RadioInputs. Django 1.4 isn't happy yet with our nose tests
        # and twisted setup.
        field = self['delivery_class']
        for widget in field.field.widget.get_renderer(field.html_name,
                                                        field.value()):
            yield widget

    # class Meta:
    #     model = models.Conversation
    #     fields = (
    #         'subject',
    #         'message',
    #         'start_date',
    #         'start_time',
    #         'delivery_class',
    #         'delivery_tag_pool',
    #     )


class ConversationGroupForm(forms.Form):
    def __init__(self, *args, **kw):
        group_names = kw.pop('group_names')
        super(ConversationGroupForm, self).__init__(*args, **kw)
        self.fields['groups'] = forms.MultipleChoiceField(
            widget=forms.CheckboxSelectMultiple,
            choices=[(n, n) for n in group_names])


class ConversationSearchForm(forms.Form):
    query = forms.CharField(required=False, widget=forms.TextInput(attrs={
        'class': 'input-xlarge',
        'id': 'search-filter-input',
        'placeholder': 'Search conversations...',
        }))
    conversation_type = forms.ChoiceField(required=False,
        choices=([('', 'Type ...')] + CONVERSATION_TYPES),
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
                        choices=get_combined_delivery_classes())
