
class ServiceComponentDefinitionBase(object):
    """Service definition base class"""

    service_component_type = None
    service_component_display_name = u"Service"
    service_component_factory = None

    def __init__(self, service=None):
        self.service = service

    def is_config_valid(self):
        raise NotImplementedError()

    def get_component(self):
        if self.service_component_factory is None:
            raise ValueError("No service component factory specified.")
        return self.service_component_factory(self)
