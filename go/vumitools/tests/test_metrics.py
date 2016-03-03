import time
from twisted.internet.defer import inlineCallbacks

from vumi.tests.helpers import VumiTestCase

from go.vumitools.metrics import (
    ConversationMetric, ConversationMetricSet, MessagesSentMetric,
    MessagesReceivedMetric, OutboundUniqueAddressesMetric,
    InboundUniqueAddressesMetric)
from go.vumitools.tests.helpers import GoMessageHelper, VumiApiHelper


class ToyConversationMetric(ConversationMetric):
    METRIC_NAME = 'dave'


class TestConversationMetrics(VumiTestCase):
    @inlineCallbacks
    def setUp(self):
        self.vumi_helper = yield self.add_helper(VumiApiHelper())
        self.msg_helper = self.add_helper(
            GoMessageHelper(vumi_helper=self.vumi_helper))
        self.user_helper = yield self.vumi_helper.make_user(u'user')
        self.patch(time, 'time', lambda: 1985)

    def test_get_target_spec(self):
        metric = ToyConversationMetric(None)
        self.assertEqual(metric.get_target_spec(), {
            'metric_type': 'conversation',
            'name': 'dave',
            'aggregator': 'avg',
        })

    def test_get_target_spec_name_override(self):
        metric = ToyConversationMetric(None, metric_name='greg')
        self.assertEqual(metric.get_target_spec(), {
            'metric_type': 'conversation',
            'name': 'greg',
            'aggregator': 'avg',
        })

    @inlineCallbacks
    def test_messages_sent_metric_value_retrieval(self):
        conv = yield self.user_helper.create_conversation(u'some_conversation')
        metric = MessagesSentMetric(conv)
        self.assertEqual(
            (yield metric.get_value(self.user_helper.user_api)), 0)

        yield self.msg_helper.make_stored_outbound(conv, "out 1")
        yield self.msg_helper.make_stored_outbound(conv, "out 2")

        self.assertEqual(
            (yield metric.get_value(self.user_helper.user_api)), 2)

    @inlineCallbacks
    def test_messages_received_metric_value_retrieval(self):
        conv = yield self.user_helper.create_conversation(u'some_conversation')
        metric = MessagesReceivedMetric(conv)
        self.assertEqual(
            (yield metric.get_value(self.user_helper.user_api)), 0)

        yield self.msg_helper.make_stored_inbound(conv, "in 1")
        yield self.msg_helper.make_stored_inbound(conv, "in 2")

        self.assertEqual(
            (yield metric.get_value(self.user_helper.user_api)), 2)

    @inlineCallbacks
    def test_outbound_unique_addresses_metric_value_retrieval(self):
        conv = yield self.user_helper.create_conversation(u'some_conversation')
        metric = OutboundUniqueAddressesMetric(conv)
        self.assertEqual(
            (yield metric.get_value(self.user_helper.user_api)), 0)

        yield self.msg_helper.make_stored_outbound(conv, "out 1")
        yield self.msg_helper.make_stored_outbound(conv, "out 2")

        self.assertEqual(
            (yield metric.get_value(self.user_helper.user_api)), 1)

        yield self.msg_helper.make_stored_outbound(
            conv, "in 1", to_addr='from-me')

        self.assertEqual(
            (yield metric.get_value(self.user_helper.user_api)), 2)

    @inlineCallbacks
    def test_inbound_unique_addresses_metric_value_retrieval(self):
        conv = yield self.user_helper.create_conversation(u'some_conversation')
        metric = InboundUniqueAddressesMetric(conv)
        self.assertEqual(
            (yield metric.get_value(self.user_helper.user_api)), 0)

        yield self.msg_helper.make_stored_inbound(conv, "in 1")
        yield self.msg_helper.make_stored_inbound(conv, "in 2")

        self.assertEqual(
            (yield metric.get_value(self.user_helper.user_api)), 1)

        yield self.msg_helper.make_stored_inbound(
            conv, "in 1", from_addr='from-me')

        self.assertEqual(
            (yield metric.get_value(self.user_helper.user_api)), 2)


class TestConversationMetricSet(VumiTestCase):
    @inlineCallbacks
    def setUp(self):
        self.vumi_helper = yield self.add_helper(VumiApiHelper())
        self.msg_helper = self.add_helper(
            GoMessageHelper(vumi_helper=self.vumi_helper))
        self.user_helper = yield self.vumi_helper.make_user(u'user')
        self.conv = yield self.user_helper.create_conversation(
            conversation_type=u'some_conversation')

    def test_get(self):
        metric_a = ToyConversationMetric(self.conv, metric_name='a')
        metrics = ConversationMetricSet(self.conv, [metric_a])
        self.assertEqual(metric_a, metrics.get('a'))

    def test_item_getting(self):
        metric_a = ToyConversationMetric(self.conv, metric_name='a')
        metrics = ConversationMetricSet(self.conv, [metric_a])
        self.assertEqual(metric_a, metrics['a'])

    def test_values(self):
        metric_a = ToyConversationMetric(self.conv, metric_name='a')
        metric_b = ToyConversationMetric(self.conv, metric_name='b')
        metrics = ConversationMetricSet(self.conv, [metric_a, metric_b])
        self.assertEqual(metrics.values(), [metric_a, metric_b])

    def test_iteration(self):
        metric_a = ToyConversationMetric(self.conv, metric_name='a')
        metric_b = ToyConversationMetric(self.conv, metric_name='b')
        metrics = ConversationMetricSet(self.conv, [metric_a, metric_b])
        self.assertEqual(list(iter(metrics.values())), [metric_a, metric_b])

    def test_append(self):
        metric_a = ToyConversationMetric(self.conv, metric_name='a')
        metrics = ConversationMetricSet(self.conv, [metric_a])
        self.assertEqual(metrics.values(), [metric_a])

        metric_b = ToyConversationMetric(self.conv, metric_name='b')
        metrics.append(metric_b)
        self.assertEqual(metrics.values(), [metric_a, metric_b])
        self.assertEqual(metrics['b'], metric_b)

    def test_extend(self):
        metric_a = ToyConversationMetric(self.conv, metric_name='a')
        metrics = ConversationMetricSet(self.conv, [metric_a])
        self.assertEqual(metrics.values(), [metric_a])

        metric_b = ToyConversationMetric(self.conv, metric_name='b')
        metric_c = ToyConversationMetric(self.conv, metric_name='c')
        metrics.extend([metric_b, metric_c])
        self.assertEqual(metrics.values(), [metric_a, metric_b, metric_c])
        self.assertEqual(metrics['b'], metric_b)
        self.assertEqual(metrics['c'], metric_c)
