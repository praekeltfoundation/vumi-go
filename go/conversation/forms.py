from django import forms

from go.vumitools.conversation import (
    CONVERSATION_TYPES, get_combined_delivery_classes)


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
        choices=[]))  # choices populated in __init__
    delivery_tag_pool = forms.CharField(required=True, widget=forms.Select(
        attrs={'class': 'input-medium'},
        choices=[]))  # choices populated in __init__

    def __init__(self, user_api, *args, **kw):
        self.user_api = user_api
        tagpool_filter = kw.pop('tagpool_filter', None)
        super(ConversationForm, self).__init__(*args, **kw)
        tagpool_set = self.user_api.tagpools()
        if tagpool_filter is not None:
            tagpool_set = tagpool_set.select(tagpool_filter)
        self.fields['delivery_tag_pool'].widget.choices = [
            (pool, tagpool_set.tagpool_display_name(pool))
            for pool in tagpool_set.pools()]
        self.fields['delivery_class'].widget.choices = [
            (delivery_class, tagpool_set.delivery_class_name(delivery_class))
            for delivery_class in tagpool_set.delivery_classes()]

    def delivery_class_widgets(self):
        # Backported hack from Django 1.4 to allow me to iterate
        # over RadioInputs. Django 1.4 isn't happy yet with our nose tests
        # and twisted setup.
        field = self['delivery_class']
        for widget in field.field.widget.get_renderer(field.html_name,
                                                        field.value()):
            yield widget


class ConversationGroupForm(forms.Form):
    def __init__(self, *args, **kw):
        groups = kw.pop('groups')
        super(ConversationGroupForm, self).__init__(*args, **kw)
        self.fields['groups'] = forms.MultipleChoiceField(
            widget=forms.CheckboxSelectMultiple,
            choices=[(g.key, g.name) for g in groups])


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
