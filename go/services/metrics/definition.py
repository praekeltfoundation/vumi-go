
from vumi.config import ConfigText

from go.services.metrics.service_component import MetricsStoreServiceComponent
from go.vumitools.service.definition import ServiceComponentDefinitionBase


class MetricsServiceComponentConfig(
        ServiceComponentDefinitionBase.CONFIG_CLASS):
    metrics_prefix = ConfigText(
        "Prefix for metrics fired by this store.", required=True)


class ServiceComponentDefinition(ServiceComponentDefinitionBase):
    service_component_type = 'metrics'
    service_component_display_name = 'Metrics store'
    service_component_factory = MetricsStoreServiceComponent
    service_component_interfaces = ('metrics',)
    CONFIG_CLASS = MetricsServiceComponentConfig
