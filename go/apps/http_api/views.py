from go.conversation.base import ConversationViews


class HttpApiConversationViews(ConversationViews):
    conversation_type = u'http_api'
    conversation_display_name = u'HTTP API'
    conversation_initiator = None
    edit_conversation_forms = None
