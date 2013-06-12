from bootstrap.forms import BootstrapForm
from django import forms

from go.vumitools.conversation.definition import (
    ConversationDefinitionBase, ConversationAction)

# NOTE: All of this stuff is assumed to be sync, so we don't yield.


class MessageForm(BootstrapForm):
    message = forms.CharField()
    dedupe = forms.BooleanField(required=False)


class BulkSendAction(ConversationAction):
    action_name = 'bulk_send'
    action_display_name = 'Send Bulk Message'

    def get_action_form(self):
        return MessageForm

    def perform_action(self, action_data):
        return self.send_command(
            'bulk_send', batch_id=self._conv.get_latest_batch_key(),
            msg_options={}, content=action_data['message'],
            dedupe=action_data['dedupe'])


class ConversationDefinition(ConversationDefinitionBase):
    conversation_type = 'bulk_message'

    actions = (BulkSendAction,)
