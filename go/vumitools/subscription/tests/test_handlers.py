from twisted.internet.defer import inlineCallbacks

from vumi.tests.helpers import VumiTestCase

from go.vumitools.subscription.handlers import SubscriptionHandler
from go.vumitools.tests.helpers import EventHandlerHelper


class TestSubscriptionHandler(VumiTestCase):

    @inlineCallbacks
    def setUp(self):
        self.eh_helper = self.add_helper(EventHandlerHelper())

        yield self.eh_helper.setup_event_dispatcher(
            'conv', SubscriptionHandler, {})

        user_helper = yield self.eh_helper.vumi_helper.get_or_create_user()
        self.contact_store = user_helper.user_api.contact_store
        contact = yield self.contact_store.new_contact(
            name=u'J Random', surname=u'Person', msisdn=u'27831234567')
        self.contact_id = contact.key
        self.eh_helper.track_event('subscription', 'conv')

    def mkevent_sub(self, operation):
        return self.eh_helper.make_event('subscription', {
            'contact_id': self.contact_id,
            'campaign_name': 'testcampaign',
            'operation': operation,
        })

    @inlineCallbacks
    def assert_subscription(self, value):
        contact = yield self.contact_store.get_contact_by_key(self.contact_id)
        self.assertEqual(contact.subscription['testcampaign'], value)

    @inlineCallbacks
    def test_subscribe(self):
        yield self.assert_subscription(None)
        yield self.eh_helper.dispatch_event(self.mkevent_sub('subscribe'))
        yield self.assert_subscription('subscribed')

    @inlineCallbacks
    def test_unsubscribe(self):
        yield self.assert_subscription(None)
        yield self.eh_helper.dispatch_event(self.mkevent_sub('unsubscribe'))
        yield self.assert_subscription('unsubscribed')

    @inlineCallbacks
    def test_subscription_churn(self):
        yield self.assert_subscription(None)
        yield self.eh_helper.dispatch_event(self.mkevent_sub('subscribe'))
        yield self.assert_subscription('subscribed')
        yield self.eh_helper.dispatch_event(self.mkevent_sub('subscribe'))
        yield self.assert_subscription('subscribed')
        yield self.eh_helper.dispatch_event(self.mkevent_sub('unsubscribe'))
        yield self.assert_subscription('unsubscribed')
        yield self.eh_helper.dispatch_event(self.mkevent_sub('subscribe'))
        yield self.assert_subscription('subscribed')
