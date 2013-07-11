from go.vumitools.conversation.definition import (
    ConversationDefinitionBase, ConversationAction)


class BulkSendAction(ConversationAction):
    action_name = 'bulk_send'
    action_display_name = 'Send Bulk Message'

    needs_confirmation = True

    needs_group = True
    needs_running = True

    def check_disabled(self):
        channels = self._conv.get_channels()
        for channel in channels:
            if channel.supports_generic_sends():
                return None
        return ("This action needs channels capable of sending"
                " messages attached to this conversation.")

    def perform_action(self, action_data):
        return self.send_command(
            'bulk_send', batch_id=self._conv.get_latest_batch_key(),
            msg_options={}, content=action_data['message'],
            delivery_class=self._conv.delivery_class,
            dedupe=action_data['dedupe'])


class ConversationDefinition(ConversationDefinitionBase):
    conversation_type = 'bulk_message'

    actions = (BulkSendAction,)
