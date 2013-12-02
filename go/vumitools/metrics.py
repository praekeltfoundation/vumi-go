from django.conf import settings
from twisted.internet.defer import inlineCallbacks, returnValue

from vumi.blinkenlights.metrics import Metric, Aggregator, AVG

from go.base import amqp


class GoMetric(object):
    """
    Encapsulates name retrieval, value retrieval and publishing for Go metrics.
    """

    AGGREGATOR = AVG

    def __init__(self, name, aggregator=None):
        if aggregator is None:
            aggregator = self.AGGREGATOR
        self.metric = Metric(name, [aggregator])

    def get_full_name(self):
        """
        This is for constructing the full, prefixed metric name in
        *Django land* if a manager is not available.
        """
        return settings.GO_METRICS_PREFIX + self.get_name()

    def get_diamondash_target(self):
        return "%s.%s" % (self.get_full_name(), self.get_aggregator_name())

    def get_name(self):
        return self.metric.name

    def get_aggregator_name(self):
        return self.metric.aggs[0]

    def get_aggregator(self):
        return Aggregator.from_name(self.get_aggregator_name())

    def get_value(self):
        """
        Should be overriden to return the value used when publishing the
        metric.
        """
        raise NotImplementedError("GoMetric.get_value() needs to be overriden")

    def publish_value(self, manager_or_connection, value):
        """
        Should do a once-off publish for the metric using a manager or
        connection capable of metric publishing, and a value.
        """
        raise NotImplementedError(
            "GoMetric.publish_value() needs to be overriden")


class DjangoMetric(GoMetric):
    """
    Base for a metric publised in *Django land*.
    """

    def __init__(self, metric_name, aggregator=None):
        name = self.make_name(metric_name)
        super(DjangoMetric, self).__init__(name, aggregator)

    @classmethod
    def make_name(self, metric_name):
        return "django.%s" % (metric_name,)

    def publish_value(self, connection, value):
        """
        Does a once-off publish for the metric using an `AmqpConnection` and
        the given metric value.
        """
        connection.publish_metric(
            self.get_full_name(),
            [self.get_aggregator()],
            value)

    def oneshot(self, value=None, connection=None, **kw):
        if value is None:
            value = self.get_value(**kw)

        if connection is None:
            connection = amqp.connection

        return self.publish_value(connection, value)


class TxMetric(GoMetric):
    """
    Base for a metric publised in *Twisted land*.
    """

    def publish_value(self, manager, value):
        manager.oneshot(self.metric, value)

    @inlineCallbacks
    def oneshot(self, manager, value=None, **kw):
        if value is None:
            value = yield self.get_value(**kw)

        returnValue(self.publish_value(manager, value))


class AccountMetric(TxMetric):
    def __init__(self, account_key, store_name, metric_name, aggregator=None):
        name = self.make_name(account_key, store_name, metric_name)
        super(AccountMetric, self).__init__(name, aggregator)

    @classmethod
    def make_name(self, account_key, store_name, metric_name):
        return "campaigns.%s.stores.%s.%s" % (
            account_key, store_name, metric_name)


class ConversationMetric(TxMetric):
    METRIC_NAME = None

    def __init__(self, conv, metric_name=None):
        if metric_name is None:
            metric_name = self.METRIC_NAME

        name = self.make_name(conv, metric_name)
        super(ConversationMetric, self).__init__(name)
        self.conv = conv

    @classmethod
    def make_name(cls, conv, metric_name):
        return "campaigns.%s.conversations.%s.%s" % (
            conv.user_account.key, conv.key, metric_name)


class MetricSet(object):
    def __init__(self, metrics=None):
        self.metrics = []
        self.metrics_by_name = {}
        self.extend(metrics or [])

    def __iter__(self):
        return iter(self.metrics)

    def __getitem__(self, name):
        return self.get(name)

    def values(self):
        return self.metrics

    def get(self, name):
        return self.metrics_by_name.get(name)

    def append(self, metric):
        self.metrics.append(metric)
        self.metrics_by_name[metric.get_name()] = metric

    def extend(self, metrics):
        for m in metrics:
            self.append(m)


class ConversationMetricSet(MetricSet):
    def __init__(self, conv, metrics=None):
        self.conv = conv
        super(ConversationMetricSet, self).__init__(metrics)

    def get(self, metric_name):
        name = ConversationMetric.make_name(self.conv, metric_name)
        return super(ConversationMetricSet, self).get(name)


class MessagesSentMetric(ConversationMetric):
    METRIC_NAME = 'messages_sent'

    def get_value(self, user_api):
        batch_id = self.conv.batch.key
        return user_api.api.mdb.batch_outbound_count(batch_id)


class MessagesReceivedMetric(ConversationMetric):
    METRIC_NAME = 'messages_received'

    def get_value(self, user_api):
        batch_id = self.conv.batch.key
        return user_api.api.mdb.batch_inbound_count(batch_id)
