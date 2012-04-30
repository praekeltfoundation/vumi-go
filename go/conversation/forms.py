from django import forms
from django.forms.util import ErrorList

from go.vumitools.conversation import (
    CONVERSATION_TYPES, get_tag_pool_names, get_delivery_class_names,
    get_combined_delivery_classes)
from vumi.persist.fields import (ListProxy, ForeignKeyProxy, ManyToManyProxy)


class VumiModelForm(forms.Form):

    FETCH_RELATED_MAP = {
        ListProxy: lambda attribute: iter(attribute),
        ForeignKeyProxy: lambda attribute: attribute.get(),
        ManyToManyProxy: lambda attribute: attribute.get_all(),
    }

    def __init__(self, data=None, files=None, auto_id='id_%s', prefix=None,
                 initial=None, error_class=ErrorList, label_suffix=':',
                 empty_permitted=False, instance=None, fetch_related=[]):
        self.fetch_related = fetch_related
        if instance:
            obj_data = self.model_to_dict(instance)
            obj_data.update(initial or {})
        else:
            obj_data = None

        super(VumiModelForm, self).__init__(data, files, auto_id, prefix,
                obj_data, error_class, label_suffix, empty_permitted)

    def model_to_dict(self, model):
        values = []
        for field in model.field_descriptors.keys():
            attr = getattr(model, field)
            if isinstance(attr, tuple(self.FETCH_RELATED_MAP.keys())):
                if field in self.fetch_related:
                    lookup = self.FETCH_RELATED_MAP[attr.__class__]
                    values.append((field, lookup(attr)))
            else:
                values.append((field, attr))
        return dict(values)


class ConversationForm(VumiModelForm):
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
