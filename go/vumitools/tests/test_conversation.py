# -*- coding: utf-8 -*-

"""Tests for go.vumitools.conversation."""

from twisted.internet.defer import inlineCallbacks
from twisted.trial.unittest import TestCase

from go.vumitools.tests.utils import model_eq, RiakTestMixin
from go.vumitools.account import AccountStore
from go.vumitools.conversation import ConversationStore
from go.vumitools.opt_out import OptOutStore
from go.vumitools.contact import ContactStore


class TestConversationStore(RiakTestMixin, TestCase):

    timeout = 10

    @inlineCallbacks
    def setUp(self):
        self.config = {'bucket_prefix': 'test.'}
        self.riak_setup()
        self.manager = self.get_riak_manager(self.config)
        yield self.riak_teardown()
        self.account_store = AccountStore(self.manager)
        self.account = yield self.account_store.new_user(u'user')
        self.optout_store = OptOutStore.from_user_account(self.account)
        self.conv_store = ConversationStore.from_user_account(self.account)
        self.contact_store = ContactStore.from_user_account(self.account)

    def tearDown(self):
        return self.riak_teardown()

    def assert_models_equal(self, m1, m2):
        self.assertTrue(model_eq(m1, m2),
                        "Models not equal:\na: %r\nb: %r" % (m1, m2))

    def assert_models_not_equal(self, m1, m2):
        self.assertFalse(model_eq(m1, m2),
                         "Models unexpectedly equal:\na: %r\nb: %r" % (m1, m2))

    @inlineCallbacks
    def test_new_conversation(self):
        conversations = yield self.conv_store.list_conversations()
        self.assertEqual([], conversations)

        conv = yield self.conv_store.new_conversation(
            u'bulk_message', u'subject', u'message')
        self.assertEqual(u'bulk_message', conv.conversation_type)
        self.assertEqual(u'subject', conv.subject)
        self.assertEqual(u'message', conv.message)
        self.assertEqual([], conv.batches.keys())

        dbconv = yield self.conv_store.get_conversation_by_key(conv.key)
        self.assert_models_equal(conv, dbconv)

    @inlineCallbacks
    def test_optout_filtering(self):
        group = yield self.contact_store.new_group(u'test-group')

        # Create two random contacts
        yield self.contact_store.new_contact(msisdn=u'+27761234567', groups=[
            group.key])
        yield self.contact_store.new_contact(msisdn=u'+27760000000', groups=[
            group.key])

        conv = yield self.conv_store.new_conversation(
            u'bulk_message', u'subject', u'message', delivery_class=u'sms')
        conv.add_group(group)
        yield conv.save()

        # Opt out the first contact
        yield self.optout_store.new_opt_out(u'msisdn', u'+27761234567', {
            'message_id': u'the-message-id'
        })
        all_addrs = yield conv.get_contacts_addresses()
        self.assertEqual(set(all_addrs), set(['+27760000000', '+27761234567']))
        optedin_addrs = yield conv.get_opted_in_addresses(self.account)
        self.assertEqual(optedin_addrs, ['+27760000000'])
