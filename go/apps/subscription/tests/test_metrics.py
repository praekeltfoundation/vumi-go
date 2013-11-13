from twisted.internet.defer import inlineCallbacks
from go.apps.subscription.metrics import SubscriptionMetric
from go.vumitools.tests.utils import TxMetricTestBase
from go.vumitools.contact import ContactStore


class ToySubscriptionMetric(SubscriptionMetric):
    METRIC_NAME = 'toy-subscription-metric'
    CONTACT_LOOKUP_KEY = 'toy-subscription'


class TestSubscriptionMetric(TxMetricTestBase):
    @inlineCallbacks
    def setUp(self):
        yield super(TestSubscriptionMetric, self).setUp()

        self.conv = yield self.create_conversation(
            conversation_type=u'some_conversation')

        self.contact_store = ContactStore.from_user_account(self.user)
        yield self.contact_store.contacts.enable_search()

        self.contact1 = yield self.contact_store.new_contact(
            name=u'contact-1',
            msisdn=u'+27831234567')

        self.contact2 = yield self.contact_store.new_contact(
            name=u'contact-2',
            msisdn=u'+27831234568')

        yield self.contact1.save()
        yield self.contact2.save()

        self.metric = ToySubscriptionMetric(self.conv, 'campaign-1')

    def test_name_construction(self):
        self.assertEqual(
            self.metric.get_full_name(),
            "go.campaigns.test-0-user.conversations.%s."
            "campaign-1.toy-subscription-metric" % self.conv.key)

    @inlineCallbacks
    def test_value_retrieval(self):
        self.assertEqual(
            (yield self.metric.get_value(self.vumi_api, self.user_api)), 0)

        self.contact1.subscription['campaign-1'] = u'toy-subscription'
        self.contact2.subscription['campaign-1'] = u'toy-subscription'

        yield self.contact1.save()
        yield self.contact2.save()

        self.assertEqual(
            (yield self.metric.get_value(self.vumi_api, self.user_api)), 2)
