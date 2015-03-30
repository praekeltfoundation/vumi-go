"""Conversation, router and channel action dispatch handlers for Go API."""

from twisted.internet.defer import maybeDeferred

from vumi.rpc import signature, Unicode, Dict

from go.config import (
    configured_conversation_types, configured_router_types,
    get_conversation_definition, get_router_definition)
from go.api.go_api.utils import GoApiSubHandler, GoApiError


class ActionError(GoApiError):
    """Raise this to report an error from within an action handler."""


class ActionDispatcherMetaClass(type):
    def __new__(mcs, name, bases, dict):
        # fish for dispatcher_type_name on sub-classes
        class_dicts = [dict] + [base.__dict__ for base in reversed(bases)]
        dispatcher_type_name = None
        for cls_dict in class_dicts:
            dispatcher_type_name = cls_dict.get("dispatcher_type_name")
            if dispatcher_type_name is not None:
                break

        # hook-up jsonrpc handlers for this classes actions
        handlers = []
        if dispatcher_type_name is not None:
            for methname, meth in dict.iteritems():
                if methname.startswith("action_"):
                    action_name = methname[len("action_"):]
                    handler = mcs.mk_jsonrpc_handler(
                        action_name, meth, dispatcher_type_name)
                    handlers.append(handler)
        for handler in handlers:
            dict[handler.__name__] = handler

        return type.__new__(mcs, name, bases, dict)

    @staticmethod
    def mk_jsonrpc_handler(name, handler, type_name):
        sig = signature(**{
            "campaign_key": Unicode("Campaign key."),
            ("%s_key" % type_name): Unicode("%s key." % type_name.title()),
            "params": Dict("Additional action paramaters.", null=True),
            "returns": Dict("Result of the action.", null=True),
        })

        jsonrpc_name = "jsonrpc_%s" % (name,)

        # we use compile and exec to get exactly the signature we need
        code = compile((
            "def %s(self, campaign_key, %s_key, params=None):"
            "    return self.dispatch_action("
            "        handler, campaign_key, %s_key, params)"
            ) % (jsonrpc_name, type_name, type_name),
            "<mk_jsonrpc_handler>", "exec")

        locs = {"handler": handler}
        exec(code, locs)
        jsonrpc_handler = sig(locs[jsonrpc_name])
        return jsonrpc_handler


class ActionDispatcher(GoApiSubHandler):
    """Dispatcher for actions on vumi.persist model instances."""

    __metaclass__ = ActionDispatcherMetaClass

    # sub-classes should set this to an appropriate name (e.g.
    # 'conversation' or 'router'.
    dispatcher_type_name = None

    def dispatch_action(self, handler, campaign_key, obj_key, params):
        user_api = self.get_user_api(campaign_key)
        d = maybeDeferred(self.get_object_by_key, user_api, obj_key)

        if params is None:
            params = {}

        def action(obj):
            return handler(self, user_api, obj, **params)

        d.addCallback(action)
        return d

    def get_object_by_key(self, user_api, key):
        raise NotImplementedError(
            "Sub-classes should implement .get_object_by_key")


class ConversationActionDispatcher(ActionDispatcher):
    dispatcher_type_name = "conversation"

    def get_object_by_key(self, user_api, conversation_key):
        return user_api.get_wrapped_conversation(conversation_key)


class RouterActionDispatcher(ActionDispatcher):
    dispatcher_type_name = "router"

    def get_object_by_key(self, user_api, router_key):
        return user_api.get_router(router_key)


class CachedDynamicSubhandler(GoApiSubHandler):

    _cached_subhandler_classes = {}

    def __init__(self, user_account_key, vumi_api):
        super(CachedDynamicSubhandler, self).__init__(
            user_account_key, vumi_api)
        subhandler_classes = self.get_cached_subhandler_classes()
        for prefix, subhandler_cls in subhandler_classes.iteritems():
            subhandler = subhandler_cls(user_account_key, vumi_api)
            self.putSubHandler(prefix, subhandler)

    @classmethod
    def get_cached_subhandler_classes(cls):
        key = "%s.%s" % (cls.__module__, cls.__name__)
        subhandler_classes = cls._cached_subhandler_classes.get(key)
        if subhandler_classes is None:
            subhandler_classes = cls.get_subhandler_classes()
            cls._cached_subhandler_classes[key] = subhandler_classes
        return subhandler_classes

    @staticmethod
    def get_subhandler_classes():
        return {}


class ConversationSubhandler(CachedDynamicSubhandler):

    @staticmethod
    def get_subhandler_classes():
        subhandler_classes = {}
        for conversation_type in configured_conversation_types().keys():
            conv_def = get_conversation_definition(conversation_type)
            if conv_def is None or conv_def.api_dispatcher_cls is None:
                continue
            subhandler_classes[conversation_type] = (
                conv_def.api_dispatcher_cls)
        return subhandler_classes


class RouterSubhandler(CachedDynamicSubhandler):

    @staticmethod
    def get_subhandler_classes():
        subhandler_classes = {}
        for router_type in configured_router_types().keys():
            router_def = get_router_definition(router_type)
            if router_def is None or router_def.api_dispatcher_cls is None:
                continue
            subhandler_classes[router_type] = router_def.api_dispatcher_cls
        return subhandler_classes
