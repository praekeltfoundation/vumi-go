from go.vumitools.conversation.definition import ConversationDefinitionBase

from go.apps.dialogue.dialogue_api import DialogueActionDispatcher
from go.apps.dialogue.utils import configured_endpoints
from go.apps.jsbox.definition import SendJsboxAction


class SendDialogueAction(SendJsboxAction):
    action_display_name = 'Send Dialogue'
    action_display_verb = 'Send dialogue now'
    action_schedule_verb = 'Schedule dialogue send'


class ConversationDefinition(ConversationDefinitionBase):
    conversation_type = 'dialogue'

    actions = (
        SendDialogueAction,
    )

    api_dispatcher_cls = DialogueActionDispatcher

    def configured_endpoints(self, config):
        return configured_endpoints(config)
