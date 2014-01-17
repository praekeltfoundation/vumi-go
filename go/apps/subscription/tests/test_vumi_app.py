# -*- coding: utf-8 -*-

"""Tests for go.vumitools.bulk_send_application"""

from twisted.internet.defer import inlineCallbacks

from vumi.tests.helpers import VumiTestCase

from go.apps.subscription.vumi_app import SubscriptionApplication
from go.apps.tests.helpers import AppWorkerHelper


class TestSubscriptionApplication(VumiTestCase):

    @inlineCallbacks
    def setUp(self):
        self.app_helper = self.add_helper(
            AppWorkerHelper(SubscriptionApplication))
        self.app = yield self.app_helper.get_app_worker({})

        self.contact = yield self.app_helper.create_contact(
            u'+27831234567', name=u'First', surname=u'Contact')

        mkhandler = lambda keyword, campaign_name, operation, reply_copy: {
            'keyword': keyword,
            'campaign_name': campaign_name,
            'operation': operation,
            'reply_copy': reply_copy,
        }
        self.conv = yield self.app_helper.create_conversation(config={
            'handlers': [
                mkhandler('foo', 'foo', 'subscribe', 'Subscribed to foo.'),
                mkhandler('bar', 'bar', 'subscribe', 'Subscribed to bar.'),
                mkhandler('stop', 'foo', 'unsubscribe', ''),
                mkhandler('stop', 'bar', 'unsubscribe', 'Unsubscribed.'),
            ]})
        yield self.app_helper.start_conversation(self.conv)

    @inlineCallbacks
    def assert_subscription(self, contact, campaign_name, value):
        # Get a new copy.
        user_helper = yield self.app_helper.vumi_helper.get_or_create_user()
        contact_store = user_helper.user_api.contact_store
        contact = yield contact_store.get_contact_by_key(contact.key)
        self.assertEqual(contact.subscription[campaign_name], value)

    def dispatch_from(self, contact, content, **kw):
        return self.app_helper.make_dispatch_inbound(
            content, from_addr=contact.msisdn, conv=self.conv, **kw)

    @inlineCallbacks
    def test_subscribe_unsubscribe(self):
        yield self.assert_subscription(self.contact, 'foo', None)
        yield self.assert_subscription(self.contact, 'bar', None)

        yield self.dispatch_from(self.contact, 'foo')
        [reply] = self.app_helper.get_dispatched_outbound()
        self.assertEqual('Subscribed to foo.', reply['content'])

        yield self.assert_subscription(self.contact, 'foo', 'subscribed')
        yield self.assert_subscription(self.contact, 'bar', None)

        yield self.dispatch_from(self.contact, 'stop')
        [_, reply] = self.app_helper.get_dispatched_outbound()
        self.assertEqual('Unsubscribed.', reply['content'])

        yield self.assert_subscription(self.contact, 'foo', 'unsubscribed')
        yield self.assert_subscription(self.contact, 'bar', 'unsubscribed')

        yield self.dispatch_from(self.contact, 'bar')
        [_, _, reply] = self.app_helper.get_dispatched_outbound()
        self.assertEqual('Subscribed to bar.', reply['content'])

        yield self.assert_subscription(self.contact, 'foo', 'unsubscribed')
        yield self.assert_subscription(self.contact, 'bar', 'subscribed')

    @inlineCallbacks
    def test_empty_message(self):
        yield self.assert_subscription(self.contact, 'foo', None)
        yield self.dispatch_from(self.contact, None)
        [reply] = self.app_helper.get_dispatched_outbound()
        self.assertEqual('Unrecognised keyword.', reply['content'])
        yield self.assert_subscription(self.contact, 'foo', None)
