from . import settings
from .exceptions import UnknownServiceType


def get_service_pkg(service_type, fromlist):
    for module, data in settings.INSTALLED_SERVICES.iteritems():
        if data['namespace'] == service_type:
            service_pkg = __import__(module, fromlist=fromlist)
            return service_pkg
    raise UnknownServiceType(
        "Can't find python package for service type: %r"
        % (service_type,))


def get_service_view_definition(service_type):
    service_pkg = get_service_pkg(
        service_type, ['definition', 'view_definition'])
    service_def = service_pkg.definition.ServiceDefinition()
    return service_pkg.view_definition.ServiceViewDefinition(service_def)
