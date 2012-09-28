from go.conversation.base import ConversationViews


class BulkSendConversationViews(ConversationViews):
    conversation_type = u'bulk_message'
    conversation_initiator = u'server'
