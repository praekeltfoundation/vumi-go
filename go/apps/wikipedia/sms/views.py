from go.conversation.base import ConversationViews


class WikipediaSMSConversationViews(ConversationViews):
    conversation_type = u'wikipedia_sms'
    conversation_display_name = u'Wikipedia USSD outbound SMS connection'
    conversation_initiator = u'server'
    edit_conversation_forms = None
    conversation_start_params = {'no_batch_tag': True}
