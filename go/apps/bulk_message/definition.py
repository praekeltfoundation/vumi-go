from go.vumitools.conversation.definition import (
    ConversationDefinitionBase, ConversationAction)


class BulkSendAction(ConversationAction):
    action_name = 'bulk_send'
    action_display_name = 'Send Bulk Message'

    needs_confirmation = True

    def perform_action(self, action_data):
        return self.send_command(
            'bulk_send', batch_id=self._conv.get_latest_batch_key(),
            msg_options={}, content=action_data['message'],
            dedupe=action_data['dedupe'])


class ConversationDefinition(ConversationDefinitionBase):
    conversation_type = 'bulk_message'

    actions = (BulkSendAction,)
