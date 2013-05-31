

class ConversationDefinitionBase(object):
    """Definition of conversation UI, lifecycle and possible actions.

    NOTE: This is a work in progress. The idea is that we can build a
    completely generic conversation UI framework that uses this definition to
    present all available functionality for any given conversation.
    """

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

    actions = ()

    def __init__(self, conv=None):
        self.conv = conv


class ConversationAction(object):
    """Definition of an action that can be performed on a conversation.

    This includes things like "send a bulk message", "display JS app logs" and
    "send initial survey questions".
    """

    action_name = None

    def __init__(self, conv):
        self._conv = conv

    def get_action_form(self):
        """Returns a Django form for setting up the action or ``None``."""
        return None

    def perform_action(self, action_data):
        """Perform whatever operations are necessary for this action."""
        pass

    def send_command(self, command_name, **params):
        return self._conv.dispatch_command(
            command_name,
            user_account_key=self._conv.user_account.key,
            conversation_key=self._conv.key,
            **params)
