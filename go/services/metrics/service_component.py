
from go.vumitools.metrics import AccountMetric


class MetricsStoreServiceComponent(object):
    def __init__(self, service_def):
        self.service_def = service_def
        self.config = service_def.get_config()
        self.account_key = self.service_def.service.user_account.key

    @property
    def metrics(self):
        raise NotImplementedError("TODO")

    def _publish_account_metric(self, account_key, store, name, value, agg):
        metric = AccountMetric(account_key, store, name, agg)
        metric.oneshot(self.metrics, value)

    def fire_metric(self, metric, value, agg):
        return self._publish_account_metric(
            self.account_key, self.config.metrics_prefix, metric, value, agg)
