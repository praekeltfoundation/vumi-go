from twisted.internet.defer import inlineCallbacks

from vumi.tests.helpers import VumiTestCase

from go.apps.subscription.definition import ConversationDefinition
from go.apps.subscription.metrics import SubscribedMetric, UnsubscribedMetric
from go.vumitools.metrics import (
    MessagesReceivedMetric, MessagesSentMetric, InboundUniqueAddressesMetric,
    OutboundUniqueAddressesMetric)
from go.vumitools.tests.helpers import VumiApiHelper


class TestSubscriptionConversationDefinition(VumiTestCase):
    @inlineCallbacks
    def setUp(self):
        self.vumi_helper = yield self.add_helper(VumiApiHelper())
        self.user_helper = yield self.vumi_helper.get_or_create_user()

        wrapped_conv = yield self.user_helper.create_conversation(
            u'subscription', config={
                'handlers': [
                    {'campaign_name': 'campaign-1'},
                    {'campaign_name': 'campaign-2'}]
            })
        self.conv = wrapped_conv.c
        self.conv_def = ConversationDefinition(self.conv)

    def test_metrics_retrieval(self):
        [m1, m2, m3, m4, m5, m6, m7, m8] = self.conv_def.get_metrics()

        self.assertEqual(m1.metric.name, 'messages_sent')
        self.assertTrue(isinstance(m1, MessagesSentMetric))

        self.assertEqual(m2.metric.name, 'messages_received')
        self.assertTrue(isinstance(m2, MessagesReceivedMetric))

        self.assertEqual(m3.metric.name, 'inbound_unique_addresses')
        self.assertTrue(isinstance(m3, InboundUniqueAddressesMetric))

        self.assertEqual(m4.metric.name, 'outbound_unique_addresses')
        self.assertTrue(isinstance(m4, OutboundUniqueAddressesMetric))

        self.assertEqual(m5.metric.name, 'campaign-1.subscribed')
        self.assertTrue(isinstance(m5, SubscribedMetric))

        self.assertEqual(m6.metric.name, 'campaign-2.subscribed')
        self.assertTrue(isinstance(m6, SubscribedMetric))

        self.assertEqual(m7.metric.name, 'campaign-1.unsubscribed')
        self.assertTrue(isinstance(m7, UnsubscribedMetric))

        self.assertEqual(m8.metric.name, 'campaign-2.unsubscribed')
        self.assertTrue(isinstance(m8, UnsubscribedMetric))
