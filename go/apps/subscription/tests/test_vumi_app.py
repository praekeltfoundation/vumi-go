# -*- coding: utf-8 -*-

"""Tests for go.vumitools.bulk_send_application"""

from twisted.internet.defer import inlineCallbacks

from vumi.middleware.tagger import TaggingMiddleware

from go.vumitools.tests.utils import AppWorkerTestCase
from go.apps.subscription.vumi_app import SubscriptionApplication


class TestSubscriptionApplication(AppWorkerTestCase):

    application_class = SubscriptionApplication
    transport_type = u'sms'

    @inlineCallbacks
    def setUp(self):
        super(TestSubscriptionApplication, self).setUp()
        self.config = self.mk_config({})
        self.app = yield self.get_application(self.config)

        # Steal app's vumi_api
        self.vumi_api = self.app.vumi_api  # YOINK!

        # Create a test user account
        self.user_account = yield self.mk_user(self.vumi_api, u'testuser')
        self.user_api = self.vumi_api.get_user_api(self.user_account.key)
        # Enable search for the contact store
        yield self.user_api.contact_store.contacts.enable_search()

        yield self.setup_tagpools()

        self.contact = yield self.user_api.contact_store.new_contact(
            name=u'First', surname=u'Contact', msisdn=u'+27831234567')

        mkhandler = lambda keyword, campaign_name, operation, reply_copy: {
            'keyword': keyword,
            'campaign_name': campaign_name,
            'operation': operation,
            'reply_copy': reply_copy,
            }
        self.conv = yield self.create_conversation(
            delivery_tag_pool=u'pool', delivery_class=self.transport_type,
            metadata={
                'handlers': [
                    mkhandler('foo', 'foo', 'subscribe', 'Subscribed to foo.'),
                    mkhandler('bar', 'bar', 'subscribe', 'Subscribed to bar.'),
                    mkhandler('stop', 'foo', 'unsubscribe', ''),
                    mkhandler('stop', 'bar', 'unsubscribe', 'Unsubscribed.'),
                    ]})
        yield self.start_conversation(self.conv)

    @inlineCallbacks
    def assert_subscription(self, contact, campaign_name, value):
        # Get a new copy.
        contact = yield self.user_api.contact_store.get_contact_by_key(
            contact.key)
        self.assertEqual(contact.subscription[campaign_name], value)

    def dispatch_from(self, contact, *args, **kw):
        kw['from_addr'] = contact.msisdn
        msg = self.mkmsg_in(*args, **kw)
        return self.dispatch_to_conv(msg, self.conv)

    def set_subscription(self, contact, subscribed, unsubscribed):
        for campaign_name in subscribed:
            contact.subscription[campaign_name] = u'subscribed'
        for campaign_name in unsubscribed:
            contact.subscription[campaign_name] = u'unsubscribed'
        return contact.save()

    @inlineCallbacks
    def test_subscribe_unsubscribe(self):
        yield self.assert_subscription(self.contact, 'foo', None)
        yield self.assert_subscription(self.contact, 'bar', None)

        yield self.dispatch_from(self.contact, 'foo')
        [reply] = yield self.get_dispatched_messages()
        self.assertEqual('Subscribed to foo.', reply['content'])

        yield self.assert_subscription(self.contact, 'foo', 'subscribed')
        yield self.assert_subscription(self.contact, 'bar', None)

        yield self.dispatch_from(self.contact, 'stop')
        [_, reply] = yield self.get_dispatched_messages()
        self.assertEqual('Unsubscribed.', reply['content'])

        yield self.assert_subscription(self.contact, 'foo', 'unsubscribed')
        yield self.assert_subscription(self.contact, 'bar', 'unsubscribed')

        yield self.dispatch_from(self.contact, 'bar')
        [_, _, reply] = yield self.get_dispatched_messages()
        self.assertEqual('Subscribed to bar.', reply['content'])

        yield self.assert_subscription(self.contact, 'foo', 'unsubscribed')
        yield self.assert_subscription(self.contact, 'bar', 'subscribed')

    @inlineCallbacks
    def test_empty_message(self):
        yield self.assert_subscription(self.contact, 'foo', None)
        yield self.dispatch_from(self.contact, None)
        [reply] = yield self.get_dispatched_messages()
        self.assertEqual('Unrecognised keyword.', reply['content'])
        yield self.assert_subscription(self.contact, 'foo', None)

    @inlineCallbacks
    def test_collect_metrics(self):
        second_contact = yield self.user_api.contact_store.new_contact(
            name=u'Second', surname=u'Contact', msisdn=u'+27831234568')
        third_contact = yield self.user_api.contact_store.new_contact(
            name=u'Third', surname=u'Contact', msisdn=u'+27831234569')
        yield self.set_subscription(self.contact, [], ['bar'])
        yield self.set_subscription(second_contact, ['foo', 'bar'], [])
        yield self.set_subscription(third_contact, ['foo'], ['bar'])

        yield self.dispatch_command(
            'collect_metrics', conversation_key=self.conv.key,
            user_account_key=self.user_account.key)
        metrics = self.poll_metrics('%s.%s' % (self.user_account.key,
                                               self.conv.key))
        self.assertEqual({
                u'foo.subscribed': [2],
                u'foo.unsubscribed': [0],
                u'bar.subscribed': [1],
                u'bar.unsubscribed': [2],
                u'messages_sent': [0],
                u'messages_received': [0],
                }, metrics)
