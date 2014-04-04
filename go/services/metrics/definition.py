from go.services.metrics.service_component import MetricsStoreServiceComponent
from go.vumitools.service.definition import ServiceComponentDefinitionBase


class ServiceComponentDefinition(ServiceComponentDefinitionBase):
    service_component_type = 'metrics'
    service_component_display_name = 'Metrics store'
    service_component_factory = MetricsStoreServiceComponent
