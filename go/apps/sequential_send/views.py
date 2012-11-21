import itertools

from django import forms

from bootstrap.forms import BootstrapForm

from go.conversation.base import ConversationViews
from go.conversation.forms import VumiModelForm


class ScheduleForm(BootstrapForm):
    recurring = forms.CharField()
    days = forms.CharField()
    time = forms.CharField()


class MessageForm(BootstrapForm):
    message = forms.CharField()


class BaseMessageFormSet(forms.formsets.BaseFormSet):
    @staticmethod
    def initial_from_metadata(data):
        return [{'message': message} for message in data]

    def to_metadata(self):
        return [form.cleaned_data['message'] for form in self
                if form.cleaned_data and not form.cleaned_data['DELETE']]


class UsedTagConversationForm(VumiModelForm):
    """HERE BE DRAGONS.

    This is a hacky temporary solution to our lack of flexible routing
    infrastructure. Basically, it lists open conversations as if they were
    tagpools containing a single tag each, with the conversation key as the
    delivery class. After collecting the data, it replaces the
    conv-key-as-delivery-class with the actual delivery class on that
    conversation.

    FIXME: Make this horribleness go away by building proper routing stuff.

    Showing the conversation key in the UI as the delivery class is an
    unavoidable side effect of the way we're building this stuff at the moment.
    I don't want to touch the templates, so we get to just live with it for
    now.
    """
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
        kw.pop('tagpool_filter', None)  # We need to filter this out.
        super(UsedTagConversationForm, self).__init__(*args, **kw)

        convs = sorted(
            user_api.active_conversations(),
            key=lambda c: c.created_at, reverse=True)
        self.conversations = [c for c in convs if not c.ended()]

        self.tag_options = self._load_tag_options()
        self.fields['delivery_tag_pool'].widget.choices = list(
            itertools.chain(self.tag_options.itervalues()))
        self.fields['delivery_class'].widget.choices = [
            (conv.key, conv.subject) for conv in self.conversations]

    def _load_tag_options(self):
        tag_options = {}
        for conv in self.conversations:
            tag_options[conv.key] = self._tag_options(conv)
        return tag_options

    def _tag_options(self, conv):
        tag = "%s:%s" % (conv.delivery_tag_pool, conv.delivery_tag)
        return [(tag, conv.delivery_tag)]

    def clean_delivery_class(self):
        for conv in self.conversations:
            if conv.key == self.cleaned_data['delivery_class']:
                return conv.delivery_class

    def tagpools_by_delivery_class(self):
        delivery_classes = []
        for conv in self.conversations:
            display_name = conv.subject
            delivery_classes.append((conv.key, [
                        (display_name, self.tag_options[conv.key])]))
            return delivery_classes

    def delivery_class_widgets(self):
        # Backported hack from Django 1.4 to allow me to iterate
        # over RadioInputs. Django 1.4 isn't happy yet with our nose tests
        # and twisted setup.
        field = self['delivery_class']
        for widget in field.field.widget.get_renderer(field.html_name,
                                                        field.value()):
            yield widget


MessageFormSet = forms.formsets.formset_factory(
    MessageForm, can_delete=True, extra=1, formset=BaseMessageFormSet)


class SequentialSendConversationViews(ConversationViews):
    conversation_type = u'sequential_send'
    conversation_display_name = u'Sequential Send'
    conversation_initiator = u'server'
    edit_conversation_forms = (
        ('schedule', ScheduleForm),
        ('messages', MessageFormSet),
        )
    conversation_start_params = {'no_batch_tag': True, 'acquire_tag': False}
    conversation_form = UsedTagConversationForm
