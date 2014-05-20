from twisted.internet.defer import inlineCallbacks

from vumi.tests.helpers import VumiTestCase

from go.apps.subscription.metrics import SubscriptionMetric
from go.vumitools.tests.helpers import VumiApiHelper


class ToySubscriptionMetric(SubscriptionMetric):
    METRIC_NAME = 'toy-subscription-metric'
    CONTACT_LOOKUP_KEY = 'toy-subscription'


class TestSubscriptionMetric(VumiTestCase):
    @inlineCallbacks
    def setUp(self):
        self.vumi_helper = yield self.add_helper(VumiApiHelper())
        self.user_helper = yield self.vumi_helper.get_or_create_user()

        self.conv = yield self.user_helper.create_conversation(
            u'some_conversation')

        contact_store = self.user_helper.user_api.contact_store

        self.contact1 = yield contact_store.new_contact(
            name=u'contact-1',
            msisdn=u'+27831234567')

        self.contact2 = yield contact_store.new_contact(
            name=u'contact-2',
            msisdn=u'+27831234568')

        yield self.contact1.save()
        yield self.contact2.save()

        self.metric = ToySubscriptionMetric(self.conv, 'campaign-1')

    def test_name_construction(self):
        self.assertEqual(
            self.metric.metric.name, "campaign-1.toy-subscription-metric")

    @inlineCallbacks
    def test_value_retrieval(self):
        self.assertEqual(
            (yield self.metric.get_value(self.user_helper.user_api)), 0)

        self.contact1.subscription['campaign-1'] = u'toy-subscription'
        self.contact2.subscription['campaign-1'] = u'toy-subscription'

        yield self.contact1.save()
        yield self.contact2.save()

        self.assertEqual(
            (yield self.metric.get_value(self.user_helper.user_api)), 2)
