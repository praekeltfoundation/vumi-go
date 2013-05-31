from go.vumitools.conversation.definition import (
    ConversationDefinitionBase, ConversationAction)


# NOTE: All of this stuff is assumed to be sync, so we don't yield.


class BulkSendAction(ConversationAction):
    action_name = 'bulk_send'

    def perform_action(self, action_data):
        return self.send_command('bulk_send',
                                 batch_id=self._conv.get_latest_batch_key(),
                                 msg_options={})


class ConversationDefinition(ConversationDefinitionBase):
    conversation_type = 'bulk_message'

    actions = (BulkSendAction,)
