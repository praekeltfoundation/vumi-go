from django.conf import settings
from twisted.internet.defer import inlineCallbacks, returnValue

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

    def __init__(self, metric_name, aggregators=None):
        name = self.make_name(metric_name)
        super(DjangoMetric, self).__init__(name, aggregators)

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
            self.get_aggregators(),
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
    def __init__(self, account_key, store_name, metric_name, aggregators=None):
        name = self.make_name(account_key, store_name, metric_name)
        super(AccountMetric, self).__init__(name, aggregators)

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
