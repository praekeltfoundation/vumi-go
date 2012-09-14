from django.forms import Form, formsets, CharField

from go.conversation.base import ConversationViews


class ScheduleForm(Form):
    recurring = CharField()
    time = CharField()


class MessageForm(Form):
    message = CharField()


class BaseMessageFormSet(formsets.BaseFormSet):
    @staticmethod
    def initial_from_metadata(data):
        return [{'message': message} for message in data]

    def to_metadata(self):
        return [form.cleaned_data['message'] for form in self
                if form.cleaned_data and not form.cleaned_data['DELETE']]


MessageFormSet = formsets.formset_factory(
    MessageForm, can_delete=True, extra=1, formset=BaseMessageFormSet)


class SequentialSendConversationViews(ConversationViews):
    conversation_type = u'sequential_send'
    conversation_display_name = u'Sequential Send'
    conversation_initiator = u'server'
    edit_conversation_forms = (
        ('schedule', ScheduleForm),
        ('messages', MessageFormSet),
        )
