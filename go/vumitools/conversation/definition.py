from go.vumitools.metrics import (
    ConversationMetricSet, MessagesSentMetric, MessagesReceivedMetric)


def detach_removed_endpoints(conv, user_account, old, new):
    conn = conv.get_connector()
    rt = user_account.routing_table

    for endpoint in set(old) - set(new):
        rt.remove_endpoint(conn, endpoint)

    rt.validate_all_entries()
    return user_account.save()


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

    metrics = (
        MessagesSentMetric,
        MessagesReceivedMetric)

    # set to an sub-class of go.api.go_api.action_dispatcher
    # .ConversationActionDispatcher to provide API methods
    api_dispatcher_cls = None

    def __init__(self, conv=None):
        self.conv = conv

    @classmethod
    def get_default_config(cls, name, description):
        """
        Override to provide conversation type-specific defaults for a
        conversation config.
        """
        return {}

    def get_actions(self):
        return [action(self.conv) for action in self.actions]

    def get_metrics(self):
        return ConversationMetricSet(
            self.conv,
            [metric(self.conv) for metric in self.metrics])

    def configured_endpoints(self, config):
        return []

    def get_endpoints(self, config):
        endpoints = list(self.extra_static_endpoints)

        for endpoint in self.configured_endpoints(config):
            if (endpoint != 'default') and (endpoint not in endpoints):
                endpoints.append(endpoint)

        return endpoints

    def update_config(self, user_account, config):
        old_endpoints = self.get_endpoints(self.conv.config)
        endpoints = self.get_endpoints(config)

        self.conv.set_config(config)
        self.conv.c.extra_endpoints = endpoints

        return detach_removed_endpoints(
            self.conv, user_account, old_endpoints, endpoints)

    def is_config_valid(self):
        raise NotImplementedError()


class ConversationAction(object):
    """Definition of an action that can be performed on a conversation.

    This includes things like "send a bulk message", "display JS app logs" and
    "send initial survey questions".
    """

    action_name = None
    # title to display for action
    action_display_name = None
    # verb phrase describing the action in second person
    action_display_verb = None
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
