import itertools

from django import forms
from django.forms.util import ErrorList

from bootstrap.forms import BootstrapForm

from go.vumitools.conversation import CONVERSATION_TYPES
from vumi.persist.fields import (ListProxy, ForeignKeyProxy, ManyToManyProxy)


class VumiModelForm(BootstrapForm):

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
            obj_data = initial

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
    subject = forms.CharField(required=True)
    message = forms.CharField(required=True, widget=forms.Textarea)
    start_date = forms.DateField(required=False)
    start_time = forms.TimeField(required=False)
    # widget choices populated in __init__
    delivery_class = forms.CharField(required=True, widget=forms.RadioSelect(
        attrs={'class': 'delivery-class-radio'},
        choices=[]))
    # widget choices populated in __init__
    delivery_tag_pool = forms.CharField(required=True)

    def __init__(self, user_api, *args, **kw):
        self.user_api = user_api
        tagpool_filter = kw.pop('tagpool_filter', None)
        super(ConversationForm, self).__init__(*args, **kw)
        self.tagpool_set = self.user_api.tagpools()
        if tagpool_filter is not None:
            self.tagpool_set = self.tagpool_set.select(tagpool_filter)
        self.tag_options = self._load_tag_options()
        self.fields['delivery_tag_pool'].widget.choices = list(
            itertools.chain(self.tag_options.itervalues()))
        self.fields['delivery_class'].widget.choices = [
            (delivery_class,
             self.tagpool_set.delivery_class_name(delivery_class))
            for delivery_class in self.tagpool_set.delivery_classes()]

    def _load_tag_options(self):
        tag_options = {}
        for pool in self.tagpool_set.pools():
            tag_options[pool] = self._tag_options(pool)
        return tag_options

    def _tag_options(self, pool):
        if self.tagpool_set.user_selects_tag(pool):
            tag_options = [("%s:%s" % tag, tag[1]) for tag
                           in self.user_api.api.tpm.free_tags(pool)]
        else:
            tag_options = [("%s:" % pool,
                            "%s (auto)" % self.tagpool_set.display_name(pool))]
        return tag_options

    def tagpools_by_delivery_class(self):
        delivery_classes = {}
        for pool in self.tagpool_set.pools():
            delivery_class = self.tagpool_set.delivery_class(pool)
            if delivery_class is None:
                continue
            display_name = self.tagpool_set.display_name(pool)
            tag_pools = delivery_classes.setdefault(delivery_class, [])
            tag_pools.append((display_name, self.tag_options[pool]))
        return sorted(delivery_classes.items())

    def delivery_class_widgets(self):
        # Backported hack from Django 1.4 to allow me to iterate
        # over RadioInputs. Django 1.4 isn't happy yet with our nose tests
        # and twisted setup.
        field = self['delivery_class']
        for widget in field.field.widget.get_renderer(field.html_name,
                                                        field.value()):
            yield widget


class ConfirmConversationForm(BootstrapForm):
    token = forms.CharField(required=True, widget=forms.HiddenInput)


class ConversationGroupForm(BootstrapForm):
    def __init__(self, *args, **kw):
        groups = kw.pop('groups')
        super(ConversationGroupForm, self).__init__(*args, **kw)
        self.fields['groups'] = forms.MultipleChoiceField(
            widget=forms.CheckboxSelectMultiple,
            choices=[(g.key, g.name) for g in groups])


class ConversationSearchForm(BootstrapForm):
    query = forms.CharField(required=False, widget=forms.TextInput(attrs={
        'class': 'input-xlarge',
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


class ReplyToMessageForm(BootstrapForm):
    in_reply_to = forms.CharField(widget=forms.HiddenInput, required=True)
    to_addr = forms.CharField(label='Send To', required=True)
    content = forms.CharField(label='Reply Message', required=True,
        widget=forms.Textarea)
