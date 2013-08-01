"""Conversation, router and channel action dispatch handlers for Go API."""

from txjsonrpc.jsonrpclib import Fault

from twisted.internet.defer import maybeDeferred

from vumi import log


class ActionError(Fault):
    """Raise this to report an error from within an action handler."""

    def __init__(self, msg, fault_code=400):
        super(ActionError, self).__init__(fault_code, msg)


class ActionDispatcher(object):
    """Dispatcher for actions on vumi.persist model instances."""

    # sub-classes should set this to an appropriate name (e.g.
    # 'conversation' or 'router'.
    dispatcher_type_name = None

    def __init__(self, user_api):
        self.user_api = user_api

    def _log_error(self, err, obj, action, params):
        log.err(err,
            "Action %(action)r on %(type_name)s %(obj)r (key: %(key)r)"
            " with params %(params)r failed." % {
                "action": action,
                "type_name": self.dispatcher_type_name,
                "obj": obj,
                "key": obj.key,
                "params": params,
                })
        return err

    def _log_success(self, result, obj, action, params):
        log.info("Performed action %r on %s %r." % (
            action, self.dispatcher_type_name, obj.key))
        return result

    def dispatch_action(self, obj, action, params):
        handler = getattr(self, "handle_%s" % action, self.unknown_action)
        d = maybeDeferred(handler, obj, **params)
        d.addErrback(self._log_error, obj, action, params)
        d.addCallback(self._log_success, obj, action, params)
        return d

    def unknown_action(self, obj, **kw):
        raise ActionError("Unknown action.")


class ConversationActionDispatcher(ActionDispatcher):
    dispatcher_type_name = "conversation"


class RouterActionDispatcher(ActionDispatcher):
    dispatcher_type_name = "router"
