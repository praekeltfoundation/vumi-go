from go.vumitools.conversation.definition import (
    ConversationDefinitionBase, ConversationAction)

from go.apps.dialogue.dialogue_api import DialogueActionDispatcher
from go.apps.jsbox.definition import SendJsboxAction


class SendDialogueAction(SendJsboxAction):
    action_display_name = 'Send Dialogue'


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

    api_dispatcher_cls = DialogueActionDispatcher
