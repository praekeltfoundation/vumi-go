

class RouterDefinitionBase(object):
    """Definition of router lifecycle and possible actions.
    """

    router_type = None
    router_display_name = 'Router'

    def __init__(self, router=None):
        self.router = router

    def is_config_valid(self):
        raise NotImplementedError()
