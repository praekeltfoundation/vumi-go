from go.vumitools.conversation.definition import (
    ConversationDefinitionBase, ConversationAction)


class SendDialogueAction(ConversationAction):
    action_name = 'send_dialogue'
    action_display_name = 'Send Dialogue'

    needs_confirmation = True

    needs_group = True
    needs_running = True

    def check_disabled(self):
        if self._conv.has_channel_supporting(generic_sends=True):
            return None
        return ("This action needs channels capable of sending"
                " messages attached to this conversation.")

    def perform_action(self, action_data):
        return self.send_command(
            'send_survey', batch_id=self._conv.get_latest_batch_key(),
            msg_options={}, is_client_initiated=False,
            delivery_class=self._conv.delivery_class)


class DownloadUserDataAction(ConversationAction):
    action_name = 'download_user_data'
    action_display_name = 'Download User Data'
    redirect_to = 'user_data'


class ConversationDefinition(ConversationDefinitionBase):
    conversation_type = 'dialogue'

    actions = (
        SendDialogueAction,
        DownloadUserDataAction,
    )
