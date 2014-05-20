
from vumi.config import Config, ConfigText, ConfigList

from go.services.metrics.service_component import MetricsStoreServiceComponent
from go.vumitools.service.definition import ServiceComponentDefinitionBase


class MetricConfig(Config):
    """
    Configuration for a metric.
    """
    name = ConfigText("Metric name.", required=True)
    aggregators = ConfigList("List of aggregation methods.", required=False)


class MetricsServiceComponentConfig(
        ServiceComponentDefinitionBase.CONFIG_CLASS):
    metrics_prefix = ConfigText(
        "Prefix for metrics fired by this store.", required=True)
    metrics = ConfigList(
        "List of allowed metrics.", required=False, default=())

    def get_metrics(self):
        return [MetricConfig(metric) for metric in self.metrics]


class ServiceComponentDefinition(ServiceComponentDefinitionBase):
    service_component_type = 'metrics'
    service_component_display_name = 'Metrics store'
    service_component_factory = MetricsStoreServiceComponent
    service_component_interfaces = ('metrics',)
    CONFIG_CLASS = MetricsServiceComponentConfig
