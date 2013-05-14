

class ConversationDefinitionBase(object):
    conversation_type = None
    conversation_display_name = 'Conversation'
    extra_views = ()

    # HACK: These will both go away when we've rewritten the conversation
    # lifecycle.
    tagpool_filter = None  # This can be "client", "server" or None.
    conversation_initiator = None  # :-(

    # If these are not None, they will override the defaults.
    # FIXME: We need a better way to do this.
    conversation_form = None
    conversation_group_form = None
    edit_conversation_forms = None
    conversation_start_params = None

    def __init__(self, conv=None):
        self.conv = conv
