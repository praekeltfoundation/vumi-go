

class ConversationDefinitionBase(object):
    """Definition of conversation lifecycle and possible actions.

    NOTE: This is a work in progress. The idea is that we can build a
    completely generic conversation UI framework that uses this definition to
    present all available functionality for any given conversation.
    """

    conversation_type = None
    conversation_display_name = 'Conversation'

    extra_static_endpoints = ()

    actions = ()

    def __init__(self, conv=None):
        self.conv = conv

    def get_actions(self):
        return [action(self.conv) for action in self.actions]

    def is_config_valid(self):
        raise NotImplementedError()


class ConversationAction(object):
    """Definition of an action that can be performed on a conversation.

    This includes things like "send a bulk message", "display JS app logs" and
    "send initial survey questions".
    """

    action_name = None
    action_display_name = None
    needs_confirmation = False

    # Some actions are only possible under certain conditions.
    needs_group = False
    needs_running = False

    redirect_to = None

    def __init__(self, conv):
        self._conv = conv

    def perform_action(self, action_data):
        """Perform whatever operations are necessary for this action."""
        pass

    def send_command(self, command_name, **params):
        return self._conv.dispatch_command(
            command_name,
            user_account_key=self._conv.user_account.key,
            conversation_key=self._conv.key,
            **params)

    def is_disabled(self):
        """Returns `None` if the action is enabled, otherwise a reason string.
        """
        if self.needs_group and not self._conv.groups.keys():
            return "This action needs a contact group."

        if self.needs_running and not self._conv.running():
            return "This action needs a running conversation."

        return self.check_disabled()

    def check_disabled(self):
        """Override in subclasses to provide custom disable logic."""
        return None
