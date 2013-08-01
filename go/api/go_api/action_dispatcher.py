"""Conversation, router and channel action dispatch handlers for Go API."""

from vumi import log


class ActionError(Exception):
    """Raise this to report an error from within an action handler."""


class ActionDispatcher(object):
    """Dispatcher for actions on vumi.persist model instances."""

    # sub-classes should set this to an appropriate name (e.g.
    # 'conversation' or 'router'.
    dispatcher_type_name = None

    def __init__(self, user_api):
        self.user_api = user_api

    def dispatch_action(self, obj, action, params):
        handler = getattr(self, "handle_%s" % action, self.unknown_action)
        try:
            return handler(obj, **params)
        except:
            log.err(None,
                "Action %(action)r on"
                " %(type_name)r %(obj)r (key: %(key)r)"
                " with params %(params)r failed." % {
                    "action": action,
                    "type_name": self.dispatcher_type_name,
                    "obj": obj,
                    "key": obj.key,
                    "params": params,
                    })
            raise

    def unknown_action(self, obj, **kw):
        raise ActionError("Unknown action.")


class ConversationActionDispatcher(ActionDispatcher):
    dispatcher_type_name = "conversation"


class RouterActionDispatcher(ActionDispatcher):
    dispatcher_type_name = "router"
