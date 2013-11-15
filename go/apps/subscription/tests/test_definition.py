from go.apps.subscription.definition import ConversationDefinition
from go.apps.subscription.metrics import SubscribedMetric, UnsubscribedMetric
from go.base.tests.helpers import GoDjangoTestCase
from go.vumitools.metrics import MessagesReceivedMetric, MessagesSentMetric
from go.vumitools.tests.helpers import VumiApiHelper


class TestSubscriptionConversationDefinition(GoDjangoTestCase):
    def setUp(self):
        self.vumi_helper = VumiApiHelper(is_sync=True)
        self.add_cleanup(self.vumi_helper.cleanup)
        self.vumi_helper.setup_vumi_api()
        self.user_helper = self.vumi_helper.get_or_create_user()

        self.conv = self.user_helper.create_conversation(
            u'subscription', config={
                'handlers': [
                    {'campaign_name': 'campaign-1'},
                    {'campaign_name': 'campaign-2'}]
            })
        self.conv_def = ConversationDefinition(self.conv)

    def test_metrics_retrieval(self):
        [m1, m2, m3, m4, m5, m6] = self.conv_def.get_metrics()

        metric_name_prefix = (
            "go.campaigns.%s.conversations.%s"
            % (self.conv.user_account.key, self.conv.key))

        self.assertEqual(
            m1.get_full_name(),
            '%s.messages_sent' % metric_name_prefix)
        self.assertTrue(isinstance(m1, MessagesSentMetric))

        self.assertEqual(
            m2.get_full_name(),
            '%s.messages_received' % metric_name_prefix)
        self.assertTrue(isinstance(m2, MessagesReceivedMetric))

        self.assertEqual(
            m3.get_full_name(),
            '%s.campaign-1.subscribed' % metric_name_prefix)
        self.assertTrue(isinstance(m3, SubscribedMetric))

        self.assertEqual(
            m4.get_full_name(),
            '%s.campaign-2.subscribed' % metric_name_prefix)
        self.assertTrue(isinstance(m4, SubscribedMetric))

        self.assertEqual(
            m5.get_full_name(),
            '%s.campaign-1.unsubscribed' % metric_name_prefix)
        self.assertTrue(isinstance(m5, UnsubscribedMetric))

        self.assertEqual(
            m6.get_full_name(),
            '%s.campaign-2.unsubscribed' % metric_name_prefix)
        self.assertTrue(isinstance(m6, UnsubscribedMetric))
