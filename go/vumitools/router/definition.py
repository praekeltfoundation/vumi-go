from go.api.go_api.action_dispatcher import RouterActionDispatcher


class RouterDefinitionBase(object):
    """Definition of router lifecycle and possible actions.
    """

    router_type = None
    router_display_name = 'Router'

    extra_static_inbound_endpoints = ()
    extra_static_outbound_endpoints = ()

    api_dispatcher_cls = RouterActionDispatcher

    def __init__(self, router=None):
        self.router = router

    def is_config_valid(self):
        raise NotImplementedError()

    def configured_inbound_endpoints(self, config):
        return []

    def configured_outbound_endpoints(self, config):
        return []
