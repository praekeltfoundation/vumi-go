from go.conversation.base import ConversationViews


class OptOutConversationViews(ConversationViews):
    conversation_type = u'opt_out'
    conversation_initiator = u'client'
    conversation_display_name = u'Opt Out Channel'
