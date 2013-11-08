from go.base.tests.utils import VumiGoDjangoTestCase
from go.vumitools.metrics import MessagesReceivedMetric, MessagesSentMetric
from go.apps.subscription.definition import ConversationDefinition
from go.apps.subscription.metrics import SubscribedMetric, UnsubscribedMetric


class TestSubscriptionConversationDefinition(VumiGoDjangoTestCase):
    def setUp(self):
        super(TestSubscriptionConversationDefinition, self).setUp()

        self.setup_user_api()
        self.conv = self.create_conversation(
            conversation_type=u'subscription',
            config={
                'handlers': [
                    {'campaign_name': 'campaign-1'},
                    {'campaign_name': 'campaign-2'}]
            })
        self.conv_def = ConversationDefinition(self.conv)

    def test_metrics_retrieval(self):
        [m1, m2, m3, m4, m5, m6] = self.conv_def.get_metrics()

        self.assertTrue(isinstance(m1, MessagesSentMetric))
        self.assertTrue(isinstance(m2, MessagesReceivedMetric))

        self.assertTrue(m3.get_full_name().endswith('campaign-1.subscribed'))
        self.assertTrue(isinstance(m3, SubscribedMetric))

        self.assertTrue(m4.get_full_name().endswith('campaign-2.subscribed'))
        self.assertTrue(isinstance(m4, SubscribedMetric))

        self.assertTrue(m5.get_full_name().endswith('campaign-1.unsubscribed'))
        self.assertTrue(isinstance(m5, UnsubscribedMetric))

        self.assertTrue(m6.get_full_name().endswith('campaign-2.unsubscribed'))
        self.assertTrue(isinstance(m6, UnsubscribedMetric))
