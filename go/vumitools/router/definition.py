class RouterDefinitionBase(object):
    """Definition of router lifecycle and possible actions.
    """

    router_type = None
    router_display_name = 'Router'

    extra_static_inbound_endpoints = ()
    extra_static_outbound_endpoints = ()

    # set to an sub-class of go.api.go_api.action_dispatcher
    # .RouterActionDispatcher to provide API methods
    api_dispatcher_cls = None

    def __init__(self, router=None):
        self.router = router

    def is_config_valid(self):
        raise NotImplementedError()

    def configured_inbound_endpoints(self, config):
        return []

    def configured_outbound_endpoints(self, config):
        return []
