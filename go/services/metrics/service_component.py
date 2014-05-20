from vumi.blinkenlights.metrics import Metric, Aggregator

from go.errors import VumiGoError
from go.vumitools.metrics import get_account_metric_prefix


class MissingMetricError(VumiGoError):
    """
    Raised when attempting to access an unregistered metric.
    """


class MetricsStoreServiceComponent(object):
    def __init__(self, service_def):
        self.service_def = service_def
        self.config = service_def.get_config()
        self.vumi_api = service_def.vumi_api
        self.user_account_key = service_def.service.user_account.key

        self.metric_manager = self.vumi_api.get_metric_manager(
            get_account_metric_prefix(
                self.user_account_key, self.config.metrics_prefix))

        for metric in self.config.get_metrics():
            aggs = metric.aggregators
            if aggs is not None:
                aggs = [Aggregator.from_name(agg) for agg in aggs]
            self.metric_manager.register(Metric(metric.name, aggs))

    def fire_metric(self, metric_name, value, publish=True):
        try:
            self.metric_manager[metric_name].set(value)
        except KeyError:
            raise MissingMetricError(
                "Unregistered metrig: %s" % (metric_name,))
        if publish:
            self.metric_manager.publish_metrics()
