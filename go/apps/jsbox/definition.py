from go.vumitools.conversation.definition import (
    ConversationDefinitionBase, ConversationAction)


class ViewLogsAction(ConversationAction):
    action_name = 'view_logs'
    action_display_name = 'View Sandbox Logs'
    redirect_to = 'jsbox_logs'


class ConversationDefinition(ConversationDefinitionBase):
    conversation_type = 'jsbox'
    conversation_display_name = 'Javascript App'

    actions = (ViewLogsAction,)

    def configured_endpoints(self, config):
        return []
