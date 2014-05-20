
from vumi.config import Config


class ServiceComponentDefinitionBase(object):
    """
    Service definition base class.

    Service definitions should subclass this and set various attributes.

    :attr str service_component_type:
        Unique (per service component definition) identifier.
    :attr str service_component_display_name:
        Human-readable name of the service component.
    :attr service_component_factory:
        Callable (probably a class) that creates the service component object.
        It will be called with the definition instance as its only parameter.
    :attr tuple service_component_interfaces:
        Tuple of interface names implemented by this service component.
    :attr CONFIG_CLASS:
        Configuration class for the service component.
    """

    service_component_type = None
    service_component_display_name = u"Service"
    service_component_factory = None
    service_component_interfaces = ()
    CONFIG_CLASS = Config

    def __init__(self, vumi_api, service=None):
        self.vumi_api = vumi_api
        self.service = service

    def get_config(self):
        return self.CONFIG_CLASS(self.service.config.copy())

    def get_component(self):
        if self.service_component_factory is None:
            raise ValueError("No service component factory specified.")
        return self.service_component_factory(self)

    def implements_interface(self, interface_name):
        return (interface_name in self.service_component_interfaces)
