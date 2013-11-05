from django.conf import settings
from twisted.internet.defer import inlineCallbacks

from vumi.blinkenlights.metrics import Metric


class GoMetric(object):
    AGGREGATORS = None

    def __init__(self, name, aggregators=None):
        if aggregators is None:
            aggregators = self.AGGREGATORS
        self.metric = Metric(name, aggregators)

    def get_full_name(self):
        """
        This is for constructing the full, prefixed metric name in django land
        if a manager is not available.
        """
        return settings.GO_METRICS_PREFIX + self.metric.name

    def get_value(self):
        raise NotImplementedError(
            "ConversationMetric.value() needs to be overriden")

    @inlineCallbacks
    def oneshot(self, manager, value=None):
        if value is None:
            value = self.get_value()
        manager.oneshot(self.metric, (yield value))


class ConversationMetric(GoMetric):
    METRIC_NAME = None

    def __init__(self, conv):
        super(ConversationMetric, self).__init__(self.make_name(conv))
        self.conv = conv

    @classmethod
    def make_name(cls, conv):
        return "campaigns.%s.conversations.%s.%s" % (
            conv.user_account.key, conv.key, cls.METRIC_NAME)


class AccountMetric(GoMetric):
    def __init__(self, account, store_name, metric_name, aggregators=None):
        name = self.make_name(account, store_name, metric_name)
        super(AccountMetric, self).__init__(name, aggregators)
        self.account = account

    @classmethod
    def make_name(self, account, store_name, metric_name):
        return "campaigns.%s.stores.%s.%s" % (
            account.key, store_name, metric_name)


class DjangoMetric(GoMetric):
    def __init__(self, metric_name, aggregators=None):
        name = self.make_name(metric_name)
        super(DjangoMetric, self).__init__(name, aggregators)

    @classmethod
    def make_name(self, metric_name):
        return "django.%s" % (metric_name,)
