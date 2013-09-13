from go.vumitools.tests.test_handler import EventHandlerTestCase

from twisted.internet.defer import inlineCallbacks


class SubscriptionHandlerTestCase(EventHandlerTestCase):

    handlers = [
        ('conv', 'go.vumitools.subscription.handlers.SubscriptionHandler', {})
    ]

    @inlineCallbacks
    def setUp(self):
        yield super(SubscriptionHandlerTestCase, self).setUp()
        self.contact_store = self.user_api.contact_store
        contact = yield self.contact_store.new_contact(
            name=u'J Random', surname=u'Person', msisdn=u'27831234567')
        self.contact_id = contact.key
        self.track_event(self.account.key, self.conversation.key,
                         'subscription', 'conv')

    def mkevent_sub(self, operation):
        return self.mkevent('subscription', {
            'contact_id': self.contact_id,
            'campaign_name': 'testcampaign',
            'operation': operation,
            }, conv_key=self.conversation.key, account_key=self.account.key)

    @inlineCallbacks
    def assert_subscription(self, value):
        contact = yield self.contact_store.get_contact_by_key(self.contact_id)
        self.assertEqual(contact.subscription['testcampaign'], value)

    @inlineCallbacks
    def test_subscribe(self):
        yield self.assert_subscription(None)
        yield self.publish_event(self.mkevent_sub('subscribe'))
        yield self.assert_subscription('subscribed')

    @inlineCallbacks
    def test_unsubscribe(self):
        yield self.assert_subscription(None)
        yield self.publish_event(self.mkevent_sub('unsubscribe'))
        yield self.assert_subscription('unsubscribed')

    @inlineCallbacks
    def test_subscription_churn(self):
        yield self.assert_subscription(None)
        yield self.publish_event(self.mkevent_sub('subscribe'))
        yield self.assert_subscription('subscribed')
        yield self.publish_event(self.mkevent_sub('subscribe'))
        yield self.assert_subscription('subscribed')
        yield self.publish_event(self.mkevent_sub('unsubscribe'))
        yield self.assert_subscription('unsubscribed')
        yield self.publish_event(self.mkevent_sub('subscribe'))
        yield self.assert_subscription('subscribed')
