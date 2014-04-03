
class ServiceComponentDefinitionBase(object):
    """Service definition base class"""

    service_component_type = None
    service_component_display_name = u"Service"

    def __init__(self, service=None):
        self.service = service

    def is_config_valid(self):
        raise NotImplementedError()
