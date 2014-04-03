
class ServiceDefinitionBase(object):
    """Service definition base class"""

    service_type = None
    service_display_name = u"Service"

    def __init__(self, service=None):
        self.service = service
