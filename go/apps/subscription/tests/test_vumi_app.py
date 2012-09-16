# -*- coding: utf-8 -*-

"""Tests for go.vumitools.bulk_send_application"""

from twisted.internet.defer import inlineCallbacks, returnValue

from vumi.middleware.tagger import TaggingMiddleware

from go.vumitools.api_worker import CommandDispatcher
from go.vumitools.api import VumiUserApi
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
        self.cmd_dispatcher = yield self.get_application({
            'transport_name': 'cmd_dispatcher',
            'worker_names': ['subscription_application'],
            }, cls=CommandDispatcher)

        # Steal app's vumi_api
        self.vumi_api = self.app.vumi_api  # YOINK!

        # Create a test user account
        self.user_account = yield self.vumi_api.account_store.new_user(
            u'testuser')
        self.user_api = VumiUserApi(self.vumi_api, self.user_account.key)
        # Enable search for the contact store
        yield self.user_api.contact_store.contacts.enable_search()

        yield self.user_api.api.declare_tags(
            [("pool", "tag1"), ("pool", "tag2")])
        yield self.user_api.api.set_pool_metadata(
            "pool", {"transport_type": "sms"})

        self.contact = yield self.user_api.contact_store.new_contact(
            name=u'First', surname=u'Contact', msisdn=u'+27831234567')

        mkhandler = lambda keyword, campaign_name, operation, reply_copy: {
            'keyword': keyword,
            'campaign_name': campaign_name,
            'operation': operation,
            'reply_copy': reply_copy,
            }
        self.conv = yield self.create_conversation(metadata={
                'handlers': [
                    mkhandler('foo', 'foo', 'subscribe', 'Subscribed to foo.'),
                    mkhandler('bar', 'bar', 'subscribe', 'Subscribed to bar.'),
                    mkhandler('stop', 'foo', 'unsubscribe', ''),
                    mkhandler('stop', 'bar', 'unsubscribe', 'Unsubscribed.'),
                    ]})
        yield self.conv.start()

    @inlineCallbacks
    def create_conversation(self, **kw):
        conversation = yield self.user_api.new_conversation(
            u'subscription', u'Subject', u'Message',
            delivery_tag_pool=u'pool', delivery_class=self.transport_type,
            **kw)
        yield conversation.save()
        returnValue(self.user_api.wrap_conversation(conversation))

    @inlineCallbacks
    def assert_subscription(self, contact, campaign_name, value):
        # Get a new copy.
        contact = yield self.user_api.contact_store.get_contact_by_key(
            contact.key)
        self.assertEqual(contact.subscription[campaign_name], value)

    def dispatch_from(self, contact, *args, **kw):
        kw['from_addr'] = contact.msisdn
        msg = self.mkmsg_in(*args, **kw)
        TaggingMiddleware.add_tag_to_msg(msg, ('pool', 'tag1'))
        return self.dispatch(msg)

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
