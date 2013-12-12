# -*- coding: utf-8 -*-

"""Tests for go.vumitools.bulk_send_application"""

from twisted.internet.defer import inlineCallbacks

from go.vumitools.tests.utils import AppWorkerTestCase
from go.apps.subscription.vumi_app import SubscriptionApplication
from go.vumitools.tests.helpers import GoMessageHelper


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
            config={
                'handlers': [
                    mkhandler('foo', 'foo', 'subscribe', 'Subscribed to foo.'),
                    mkhandler('bar', 'bar', 'subscribe', 'Subscribed to bar.'),
                    mkhandler('stop', 'foo', 'unsubscribe', ''),
                    mkhandler('stop', 'bar', 'unsubscribe', 'Unsubscribed.'),
                ]})
        yield self.start_conversation(self.conv)
        self.msg_helper = self.add_helper(
            GoMessageHelper(self.user_api.api.mdb))

    @inlineCallbacks
    def assert_subscription(self, contact, campaign_name, value):
        # Get a new copy.
        contact = yield self.user_api.contact_store.get_contact_by_key(
            contact.key)
        self.assertEqual(contact.subscription[campaign_name], value)

    def dispatch_from(self, contact, content, **kw):
        kw['from_addr'] = contact.msisdn
        msg = self.msg_helper.make_inbound(content, **kw)
        return self.dispatch_to_conv(msg, self.conv)

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
