# -*- coding: utf-8 -*-

"""Tests for go.vumitools.conversation."""

from twisted.internet.defer import inlineCallbacks
from twisted.trial.unittest import TestCase

from go.vumitools.tests.utils import model_eq, GoPersistenceMixin
from go.vumitools.account import AccountStore
from go.vumitools.conversation import ConversationStore
from go.vumitools.opt_out import OptOutStore
from go.vumitools.contact import ContactStore


class TestConversationStore(GoPersistenceMixin, TestCase):

    timeout = 10

    @inlineCallbacks
    def setUp(self):
        self._persist_setUp()
        self.manager = self.get_riak_manager()
        self.account_store = AccountStore(self.manager)
        self.account = yield self.account_store.new_user(u'user')
        self.optout_store = OptOutStore.from_user_account(self.account)
        self.conv_store = ConversationStore.from_user_account(self.account)
        self.contact_store = ContactStore.from_user_account(self.account)

    def tearDown(self):
        return self._persist_tearDown()

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
