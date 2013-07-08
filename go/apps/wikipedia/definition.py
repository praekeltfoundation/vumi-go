from go.vumitools.conversation.definition import ConversationDefinitionBase


class ConversationDefinition(ConversationDefinitionBase):
    conversation_type = u'wikipedia'
    conversation_display_name = u'Wikipedia'

    extra_static_endpoints = (u'sms_content',)
