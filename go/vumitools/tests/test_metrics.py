import time
from mock import patch
from twisted.internet.defer import succeed, inlineCallbacks

from vumi.worker import BaseWorker

from go.base.amqp import AmqpConnection
from go.vumitools.metrics import (
    GoMetric, DjangoMetric, TxMetric, ConversationMetric, AccountMetric,
    MetricSet, ConversationMetricSet, MessagesSentMetric,
    MessagesReceivedMetric)
from go.vumitools.app_worker import GoWorkerMixin, GoWorkerConfigMixin
from go.vumitools.tests.utils import TxMetricTestBase, GoTestCase
from go.vumitools.tests.helpers import GoMessageHelper
from go.base.tests.utils import VumiGoDjangoTestCase


class ToyGoMetric(GoMetric):
    pass


class ToyTxMetric(TxMetric):
    def __init__(self, *a, **kw):
        super(ToyTxMetric, self).__init__(*a, **kw)
        self.value = None

    def set_value(self, value):
        self.value = value

    def get_value(self):
        return self.value


class ToyDjangoMetric(DjangoMetric):
    def __init__(self, *a, **kw):
        super(ToyDjangoMetric, self).__init__(*a, **kw)
        self.value = None

    def set_value(self, value):
        self.value = value

    def get_value(self):
        return self.value


class ToyWorkerConfig(BaseWorker.CONFIG_CLASS, GoWorkerConfigMixin):
    pass


class ToyWorker(BaseWorker, GoWorkerMixin):
    CONFIG_CLASS = ToyWorkerConfig

    def setup_worker(self):
        return self._go_setup_worker()

    def teardown_worker(self):
        return self._go_teardown_worker()

    def setup_connectors(self):
        pass


class ToyConversationMetric(ConversationMetric):
    METRIC_NAME = 'dave'


class TestGoMetric(GoTestCase):
    @inlineCallbacks
    def setUp(self):
        yield super(TestGoMetric, self).setUp()
        self.metric = ToyGoMetric('some.random.metric')

    def test_full_name_retrieval(self):
        self.assertEqual(self.metric.get_full_name(), 'go.some.random.metric')

    def test_diamondash_target_name_retrieval(self):
        self.assertEqual(
            self.metric.get_diamondash_target(),
            'go.some.random.metric.avg')


class TestDjangoMetric(VumiGoDjangoTestCase):
    def setUp(self):
        super(TestDjangoMetric, self).setUp()
        self.metric = ToyDjangoMetric('luke')

        self.time_patcher = patch('time.time')
        mock_time = self.time_patcher.start()
        mock_time.side_effect = lambda: 1985

        self.msgs = []
        self.publish_patcher = patch(
            'go.base.amqp.connection.publish_metric_message')
        mock_publish = self.publish_patcher.start()
        mock_publish.side_effect = self.mock_publish

    def mock_publish(self, msg):
        self.msgs.append(msg)

    def tearDown(self):
        super(TestDjangoMetric, self).tearDown()
        self.time_patcher.stop()
        self.publish_patcher.stop()

    def test_name_construction(self):
        self.assertEqual(
            self.metric.get_full_name(),
            u'go.django.luke')

    def test_oneshot(self):
        self.metric.set_value(23)
        self.assertEqual(self.msgs, [])
        self.metric.oneshot()

        [msg] = self.msgs
        self.assertEqual(
            msg['datapoints'],
            [('go.django.luke', ('avg',), [(1985, 23)])])

    def make_connection(self):
        connection = AmqpConnection()
        connection.publish_metric_message = self.mock_publish
        return connection

    def test_oneshot_with_explicitly_given_connection(self):
        self.metric.set_value(23)
        self.assertEqual(self.msgs, [])
        self.metric.oneshot(connection=self.make_connection())

        [msg] = self.msgs
        self.assertEqual(
            msg['datapoints'],
            [('go.django.luke', ('avg',), [(1985, 23)])])

    def test_oneshot_with_value(self):
        self.assertEqual(self.msgs, [])
        self.metric.oneshot(value=22)

        [msg] = self.msgs
        self.assertEqual(
            msg['datapoints'],
            [('go.django.luke', ('avg',), [(1985, 22)])])


class TestTxMetric(TxMetricTestBase):
    @inlineCallbacks
    def setUp(self):
        yield super(TestTxMetric, self).setUp()
        self.patch(time, 'time', lambda: 1985)
        self.metric = ToyTxMetric('some.random.metric')

    def test_oneshot(self):
        self.metric.set_value(23)
        self.metric.oneshot(self.metrics_manager)
        self.assertEqual(self.msgs, [])

        self.publish_metrics()

        [msg] = self.msgs
        self.assertEqual(
            msg['datapoints'],
            [('go.some.random.metric', ('avg',), [(1985, 23)])])

    @inlineCallbacks
    def test_oneshot_for_deferred_values(self):
        self.metric.set_value(succeed(42))
        yield self.metric.oneshot(self.metrics_manager)

        self.assertEqual(self.msgs, [])

        self.publish_metrics()

        [msg] = self.msgs
        self.assertEqual(
            msg['datapoints'],
            [('go.some.random.metric', ('avg',), [(1985, 42)])])

    def test_oneshot_with_value(self):
        self.metric.oneshot(self.metrics_manager, value=9)

        self.assertEqual(self.msgs, [])

        self.publish_metrics()

        [msg] = self.msgs
        self.assertEqual(
            msg['datapoints'],
            [('go.some.random.metric', ('avg',), [(1985, 9)])])


class TestConversationMetric(TxMetricTestBase):
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


class TestAccountMetric(TxMetricTestBase):
    @inlineCallbacks
    def setUp(self):
        yield super(TestAccountMetric, self).setUp()
        self.metric = AccountMetric(self.user.key, 'store-1', 'susan')

    def test_name_construction(self):
        self.assertEqual(
            self.metric.get_full_name(),
            u'go.campaigns.test-0-user.stores.store-1.susan')


class TestMessagesSentMetric(TxMetricTestBase):
    @inlineCallbacks
    def setUp(self):
        yield super(TestMessagesSentMetric, self).setUp()

        self.msg_helper = GoMessageHelper(self.user_api.api.mdb)

        self.conv = yield self.create_conversation(
            conversation_type=u'some_conversation')

        self.metric = MessagesSentMetric(self.conv)

    @inlineCallbacks
    def test_value_retrieval(self):
        self.assertEqual(
            (yield self.metric.get_value(self.user_api)), 0)

        yield self.msg_helper.make_stored_outbound(self.conv, "out 1")
        yield self.msg_helper.make_stored_outbound(self.conv, "out 2")

        self.assertEqual(
            (yield self.metric.get_value(self.user_api)), 2)


class TestMessagesReceivedMetric(TxMetricTestBase):
    @inlineCallbacks
    def setUp(self):
        yield super(TestMessagesReceivedMetric, self).setUp()

        self.msg_helper = GoMessageHelper(self.user_api.api.mdb)

        self.conv = yield self.create_conversation(
            conversation_type=u'some_conversation')

        self.metric = MessagesReceivedMetric(self.conv)

    @inlineCallbacks
    def test_value_retrieval(self):
        self.assertEqual(
            (yield self.metric.get_value(self.user_api)), 0)

        yield self.msg_helper.make_stored_inbound(self.conv, "in 1")
        yield self.msg_helper.make_stored_inbound(self.conv, "in 2")

        self.assertEqual(
            (yield self.metric.get_value(self.user_api)), 2)


class TestMetricSet(GoTestCase):
    @inlineCallbacks
    def setUp(self):
        yield super(TestMetricSet, self).setUp()

        self.metric_a = ToyGoMetric('a')
        self.metric_b = ToyGoMetric('b')
        self.metric_c = ToyGoMetric('c')

        self.metrics = MetricSet([
            self.metric_a,
            self.metric_b,
            self.metric_c
        ])

    def test_item_getting(self):
        self.assertEqual(self.metric_a, self.metrics['a'])

    def test_iteration(self):
        metrics = []

        for metric in self.metrics:
            metrics.append(metric)

        self.assertEqual(self.metrics.values(), [
            self.metric_a,
            self.metric_b,
            self.metric_c
        ])

    def test_get(self):
        self.assertEqual(self.metric_a, self.metrics.get('a'))

    def test_values(self):
        self.assertEqual(self.metrics.values(), [
            self.metric_a,
            self.metric_b,
            self.metric_c
        ])

    def test_append(self):
        metric_d = ToyGoMetric('d')
        self.metrics.append(metric_d)

        self.assertEqual(self.metrics.values(), [
            self.metric_a,
            self.metric_b,
            self.metric_c,
            metric_d
        ])

        self.assertEqual(self.metrics['d'], metric_d)

    def test_extend(self):
        metric_d = ToyGoMetric('d')
        metric_e = ToyGoMetric('e')
        self.metrics.extend([metric_d, metric_e])

        self.assertEqual(self.metrics.values(), [
            self.metric_a,
            self.metric_b,
            self.metric_c,
            metric_d,
            metric_e,
        ])

        self.assertEqual(self.metrics['d'], metric_d)
        self.assertEqual(self.metrics['e'], metric_e)


class TestConversationMetricSet(TxMetricTestBase):
    @inlineCallbacks
    def setUp(self):
        yield super(TestConversationMetricSet, self).setUp()

        self.conv = yield self.create_conversation(
            conversation_type=u'some_conversation')

        self.metric_a = ToyConversationMetric(self.conv, metric_name='a')
        self.metrics = ConversationMetricSet(self.conv, [self.metric_a])

    def test_get(self):
        self.assertEqual(self.metric_a, self.metrics.get('a'))
