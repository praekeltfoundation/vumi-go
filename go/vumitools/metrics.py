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

    def oneshot_with_value(self, value):
        """
        Should do a once-off publish for the metric using the given value.
        """
        raise NotImplementedError(
            "GoMetric.oneshot_with_value() needs to be overriden")

    def oneshot(self, *a, **kw):
        """
        Should do a once-off publish for the metric using `get_value()` to
        calculate the metric's value.
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

    def oneshot_with_value(self, value, connection=None):
        """
        Does a once-off publish for the metric using an `AmqpConnection` and
        the given metric value.
        """

        if connection is None:
            connection = amqp.connection

        connection.publish_metric(
            self.get_full_name(),
            self.get_aggregators(),
            value)

    def oneshot(self, connection=None):
        """
        Obtains a value using `get_value()`, then does a once-off publish for
        the metric using an `AmqpConnection`.
        """
        return self.oneshot_with_value(self.get_value(), connection)


class TxMetric(GoMetric):
    """
    Base for a metric publised in *Twisted land*.
    """

    def oneshot_with_value(self, manager, value):
        manager.oneshot(self.metric, value)

    @inlineCallbacks
    def oneshot(self, manager, *value_args, **value_kwargs):
        value = yield self.get_value(*value_args, **value_kwargs)
        self.oneshot_with_value(manager, value)


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

    def get_value(self, vumi_api, user_api):
        batch_id = self.conv.batch.key
        return vumi_api.mdb.batch_outbound_count(batch_id)


class MessagesReceivedMetric(ConversationMetric):
    METRIC_NAME = 'messages_received'

    def get_value(self, vumi_api, user_api):
        batch_id = self.conv.batch.key
        return vumi_api.mdb.batch_inbound_count(batch_id)
