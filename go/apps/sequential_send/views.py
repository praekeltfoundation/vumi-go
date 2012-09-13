from django.forms import Form, formsets, CharField

from go.conversation.base import ConversationViews, EditConversationView


class MessageForm(Form):
    message = CharField()


class SequentialSendForm(Form):
    pass


MessageFormSet = formsets.formset_factory(
    MessageForm, can_delete=True, extra=1)


class EditSequentialSendConversationView(EditConversationView):
    def make_form(self, conversation):
        metadata = conversation.get_metadata()
        print metadata
        if metadata is None:
            metadata = {'messages': []}
        messages = [{'message': message} for message in metadata['messages']]
        return self.edit_conversation_form(initial=messages)

    def process_form(self, conversation, form):
        metadata = {'messages': [f.cleaned_data['message'] for f in form]}
        conversation.set_metadata(metadata)
        conversation.save()
        return metadata


class SequentialSendConversationViews(ConversationViews):
    conversation_type = u'sequential_send'
    conversation_display_name = u'Sequential Send'
    conversation_initiator = u'server'
    edit_conversation_form = MessageFormSet

    edit_conversation_view = EditSequentialSendConversationView
