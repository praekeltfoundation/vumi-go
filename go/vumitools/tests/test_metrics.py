import time

from twisted.internet.defer import succeed, inlineCallbacks

from vumi.worker import BaseWorker
from vumi.blinkenlights.metrics import LAST

from go.vumitools.metrics import (
    GoMetric, ConversationMetric, AccountMetric, DjangoMetric)
from go.vumitools.tests.utils import GoWorkerTestCase
from go.vumitools.app_worker import GoWorkerMixin, GoWorkerConfigMixin


class ToyGoMetric(GoMetric):
    AGGREGATORS = [LAST]

    def __init__(self, *a, **kw):
        super(ToyGoMetric, self).__init__(*a, **kw)
        self.value = None

    def set_value(self, value):
        self.value = value

    def get_value(self):
        return self.value


class ToyWorkerConfig(BaseWorker.CONFIG_CLASS, GoWorkerConfigMixin):
    pass


class ToyConversationMetric(ConversationMetric):
    METRIC_NAME = 'dave'


class ToyWorker(BaseWorker, GoWorkerMixin):
    CONFIG_CLASS = ToyWorkerConfig

    def setup_worker(self):
        return self._go_setup_worker()

    def teardown_worker(self):
        return self._go_teardown_worker()

    def setup_connectors(self):
        pass


class TestGoMetricBase(GoWorkerTestCase):
    worker_class = ToyWorker

    @inlineCallbacks
    def setUp(self):
        super(TestGoMetricBase, self).setUp()
        worker_config = self.mk_config({'metrics_prefix': 'go.'})

        self.worker = yield self.get_worker(worker_config, start=True)
        self.vumi_api = self.worker.vumi_api

        self.user = yield self.mk_user(self.vumi_api, u'testuser')
        self.user_api = self.vumi_api.get_user_api(self.user.key)


class TestGoMetric(TestGoMetricBase):
    @inlineCallbacks
    def setUp(self):
        yield super(TestGoMetric, self).setUp()

        self.metrics_manager = self.worker.metrics
        self.metric = ToyGoMetric('some.random.metric')

        self.patch(time, 'time', lambda: 1985)

        self.msgs = []
        self.patch(
            self.metrics_manager,
            'publish_message', lambda msg: self.msgs.append(msg))

    def publish_metrics(self):
        self.metrics_manager._publish_metrics()

    def test_oneshot(self):
        self.metric.set_value(23)
        self.metric.oneshot(self.metrics_manager)
        self.assertEqual(self.msgs, [])

        self.publish_metrics()

        [msg] = self.msgs
        self.assertEqual(
            msg['datapoints'],
            [('go.some.random.metric', ('last',), [(1985, 23)])])

    @inlineCallbacks
    def test_oneshot_for_deferred_values(self):
        self.metric.set_value(succeed(42))
        yield self.metric.oneshot(self.metrics_manager)

        self.assertEqual(self.msgs, [])

        self.publish_metrics()

        [msg] = self.msgs
        self.assertEqual(
            msg['datapoints'],
            [('go.some.random.metric', ('last',), [(1985, 42)])])

    def test_oneshot_for_explicitly_given_values(self):
        self.metric.oneshot(self.metrics_manager, 9)

        self.assertEqual(self.msgs, [])

        self.publish_metrics()

        [msg] = self.msgs
        self.assertEqual(
            msg['datapoints'],
            [('go.some.random.metric', ('last',), [(1985, 9)])])

    def test_full_name_retrieval(self):
        self.assertEqual(self.metric.get_full_name(), 'go.some.random.metric')


class TestConversationMetric(TestGoMetricBase):
    @inlineCallbacks
    def setUp(self):
        yield super(TestConversationMetric, self).setUp()

        self.conv = yield self.create_conversation(
            conversation_type=u'some_conversation')

        self.metric = ToyConversationMetric(self.conv)

    def test_name_construction(self):
        self.assertEqual(
            self.metric.get_full_name(),
            'go.campaigns.test-0-user.conversations.%s.dave' % self.conv.key)


class TestAccountMetric(TestGoMetricBase):
    @inlineCallbacks
    def setUp(self):
        yield super(TestAccountMetric, self).setUp()
        self.metric = AccountMetric(self.user, 'store-1', 'susan')

    def test_name_construction(self):
        self.assertEqual(
            self.metric.get_full_name(),
            u'go.campaigns.test-0-user.stores.store-1.susan')


class TestDjangoMetric(TestGoMetricBase):
    @inlineCallbacks
    def setUp(self):
        yield super(TestDjangoMetric, self).setUp()
        self.metric = DjangoMetric('luke')

    def test_name_construction(self):
        self.assertEqual(
            self.metric.get_full_name(),
            u'go.django.luke')
