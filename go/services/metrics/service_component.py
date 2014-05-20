
from go.vumitools.metrics import get_account_metric_prefix


class MetricsStoreServiceComponent(object):
    def __init__(self, service_def):
        self.service_def = service_def
        self.config = service_def.get_config()
        self.vumi_api = service_def.vumi_api
        self.user_account_key = service_def.service.user_account.key

    @property
    def metrics(self):
        raise NotImplementedError("TODO")

    def fire_metric(self, metric, value):
        metrics = self.vumi_api.get_metric_manager(get_account_metric_prefix(
            self.user_account_key, self.config.metrics_prefix))
        metrics.oneshot(metric, value)
        return metrics.publish_metrics()
