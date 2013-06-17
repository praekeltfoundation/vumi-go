from go.vumitools.conversation.definition import (
    ConversationDefinitionBase, ConversationAction)


class SendSurveyAction(ConversationAction):
    action_name = 'send_survey'
    action_display_name = 'Send Survey'

    def perform_action(self, action_data):
        return self.send_command(
            'send_survey', batch_id=self._conv.get_latest_batch_key(),
            msg_options={}, is_client_initiated=False)


class DownloadUserDataAction(ConversationAction):
    action_name = 'download_user_data'
    action_display_name = 'Download User Data'
    redirect_to = 'user_data'


class ConversationDefinition(ConversationDefinitionBase):
    conversation_type = 'surveys'

    actions = (
        SendSurveyAction,
        DownloadUserDataAction,
    )
