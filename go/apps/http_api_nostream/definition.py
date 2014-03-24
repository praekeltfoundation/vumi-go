from go.vumitools.conversation.definition import ConversationDefinitionBase

DEFAULT_METRIC_STORE = 'default'


class ConversationDefinition(ConversationDefinitionBase):
    conversation_type = u'http_api_nostream'
