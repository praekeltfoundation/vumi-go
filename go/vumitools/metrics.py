from vumi.blinkenlights.metrics import Metric, AVG

from go.config import get_go_metrics_prefix


class ConversationMetric(object):
    """
    A wrapper around a metric object that knows how to collect data.
    """

    AGGREGATOR = AVG
    METRIC_NAME = None

    def __init__(self, conv, metric_name=None):
        self.conv = conv
        if metric_name is None:
            metric_name = self.METRIC_NAME
        self.metric = Metric(metric_name, [self.AGGREGATOR])

    def get_target_spec(self):
        return {
            'metric_type': 'conversation',
            'name': self.metric.name,
            'aggregator': self.AGGREGATOR.name,
        }

    def get_value(self, user_api):
        """
        Should be overriden to return the value used when publishing the
        metric.
        """
        raise NotImplementedError(
            "ConversationMetric.get_value() needs to be overriden")


class ConversationMetricSet(object):
    def __init__(self, conv, metrics=None):
        self.conv = conv
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
        self.metrics_by_name[metric.metric.name] = metric

    def extend(self, metrics):
        for m in metrics:
            self.append(m)


class MessagesSentMetric(ConversationMetric):
    METRIC_NAME = 'messages_sent'

    def get_value(self, user_api):
        batch_id = self.conv.batch.key
        qms = user_api.api.get_query_message_store()
        return qms.get_batch_outbound_count(batch_id)


class MessagesReceivedMetric(ConversationMetric):
    METRIC_NAME = 'messages_received'

    def get_value(self, user_api):
        batch_id = self.conv.batch.key
        qms = user_api.api.get_query_message_store()
        return qms.get_batch_inbound_count(batch_id)


def get_account_metric_prefix(account_key, store):
    return "%scampaigns.%s.stores.%s." % (
        get_go_metrics_prefix(), account_key, store)


def get_conversation_metric_prefix(conv):
    return "%scampaigns.%s.conversations.%s." % (
        get_go_metrics_prefix(), conv.user_account.key, conv.key)


def get_django_metric_prefix():
    return "%sdjango." % (get_go_metrics_prefix(),)
