# -*- coding: utf-8 -*-

"""Tests for go.vumitools.bulk_send_application"""

from twisted.internet.defer import inlineCallbacks

from vumi.tests.helpers import VumiTestCase

from go.apps.subscription.vumi_app import SubscriptionApplication
from go.apps.tests.helpers import AppWorkerHelper


class TestSubscriptionApplication(VumiTestCase):

    @inlineCallbacks
    def setUp(self):
        self.app_helper = AppWorkerHelper(SubscriptionApplication)
        self.add_cleanup(self.app_helper.cleanup)
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

    @inlineCallbacks
    def test_collect_metrics(self):
        second_contact = yield self.app_helper.create_contact(
            u'+27831234568', name=u'Second', surname=u'Contact')
        third_contact = yield self.app_helper.create_contact(
            u'+27831234569', name=u'Third', surname=u'Contact')
        yield self.set_subscription(self.contact, [], ['bar'])
        yield self.set_subscription(second_contact, ['foo', 'bar'], [])
        yield self.set_subscription(third_contact, ['foo'], ['bar'])

        yield self.app_helper.dispatch_command(
            'collect_metrics', conversation_key=self.conv.key,
            user_account_key=self.conv.user_account.key)

        prefix = "campaigns.test-0-user.conversations.%s" % self.conv.key

        self.assertEqual(
            self.app_helper.get_published_metrics(self.app),
            [("%s.foo.subscribed" % prefix, 2),
             ("%s.foo.unsubscribed" % prefix, 0),
             ("%s.bar.subscribed" % prefix, 1),
             ("%s.bar.unsubscribed" % prefix, 2),
             ("%s.messages_sent" % prefix, 0),
             ("%s.messages_received" % prefix, 0)])
