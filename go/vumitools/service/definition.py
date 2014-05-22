from vumi.config import IConfigData, Config
from zope.interface import implements

from go.config import get_service_component_config


class ServiceComponentConfigData(object):
    implements(IConfigData)
    # TODO: Replace this with better config machinery

    def __init__(self, static_config, dynamic_config):
        self._static_config = static_config
        self._dynamic_config = dynamic_config

    def get(self, field_name, default):
        if field_name in self._dynamic_config:
            return self._dynamic_config[field_name]
        return self._static_config.get(field_name, default)

    def has_key(self, field_name):
        if field_name in self._dynamic_config:
            return True
        return field_name in self._static_config


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
        static = get_service_component_config(self.service_component_type)
        return self.CONFIG_CLASS(ServiceComponentConfigData(
            static, self.service.config.copy()))

    def get_component(self):
        if self.service_component_factory is None:
            raise ValueError("No service component factory specified.")
        return self.service_component_factory(self)

    def implements_interface(self, interface_name):
        return (interface_name in self.service_component_interfaces)
