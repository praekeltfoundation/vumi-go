from django.conf import settings
from twisted.internet.defer import inlineCallbacks

from vumi.blinkenlights.metrics import Metric, Aggregator

from go.base import amqp


class GoMetric(object):
    """
    Encapsulates name retrieval, value retrieval and publishing for Go metrics.
    """

    AGGREGATORS = None

    def __init__(self, name, aggregators=None):
        if aggregators is None:
            aggregators = self.AGGREGATORS
        self.metric = Metric(name, aggregators)

    def get_full_name(self):
        """
        This is for constructing the full, prefixed metric name in
        *Django land* if a manager is not available.
        """
        return settings.GO_METRICS_PREFIX + self.metric.name

    def get_value(self):
        """
        Should be overriden to return the value used when publishing the
        metric.
        """
        raise NotImplementedError("GoMetric.get_value() needs to be overriden")

    def get_aggregators(self):
        return [Aggregator.from_name(name) for name in self.metric.aggs]

    def oneshot(self, *a, **kw):
        """
        Should do a once-off publish for the metric.
        """
        raise NotImplementedError("GoMetric.oneshot() needs to be overriden")


class DjangoMetric(GoMetric):
    """
    Base for a metric publised in *Django land*.
    """

    def __init__(self, metric_name, aggregators=None):
        name = self.make_name(metric_name)
        super(DjangoMetric, self).__init__(name, aggregators)

    @classmethod
    def make_name(self, metric_name):
        return "django.%s" % (metric_name,)

    def oneshot(self, value=None, connection=None):
        """
        Does a once-off publish for the metric using an `AmqpConnection`.
        """
        if connection is None:
            connection = amqp.connection

        if value is None:
            value = self.get_value()

        connection.publish_metric(
            self.get_full_name(),
            self.get_aggregators(),
            value)


class TxMetric(GoMetric):
    """
    Base for a metric publised in *Twisted land*.
    """

    @inlineCallbacks
    def oneshot(self, manager, value=None):
        """
        Does a once-off publish for the metric using a `MetricManager` (as
        opposed to relying on the manager to do periodic publishing).
        """
        if value is None:
            value = self.get_value()
        manager.oneshot(self.metric, (yield value))


class ConversationMetric(TxMetric):
    METRIC_NAME = None

    def __init__(self, conv):
        super(ConversationMetric, self).__init__(self.make_name(conv))
        self.conv = conv

    @classmethod
    def make_name(cls, conv):
        return "campaigns.%s.conversations.%s.%s" % (
            conv.user_account.key, conv.key, cls.METRIC_NAME)


class AccountMetric(TxMetric):
    def __init__(self, account_key, store_name, metric_name, aggregators=None):
        name = self.make_name(account_key, store_name, metric_name)
        super(AccountMetric, self).__init__(name, aggregators)

    @classmethod
    def make_name(self, account_key, store_name, metric_name):
        return "campaigns.%s.stores.%s.%s" % (
            account_key, store_name, metric_name)
