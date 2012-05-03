# -*- coding: utf-8 -*-

"""Tests for go.vumitools.conversation."""

from twisted.internet.defer import inlineCallbacks
from twisted.trial.unittest import TestCase

from vumi.persist.txriak_manager import TxRiakManager

from go.vumitools.tests.utils import model_eq
from go.vumitools.account import AccountStore
from go.vumitools.conversation import ConversationStore


class TestConversationStore(TestCase):

    timeout = 10

    @inlineCallbacks
    def setUp(self):
        self.manager = TxRiakManager.from_config({'bucket_prefix': 'test.'})
        yield self.manager.purge_all()
        self.account_store = AccountStore(self.manager)
        account = yield self.account_store.new_user(u'user')
        self.store = ConversationStore.from_user_account(account)

    def tearDown(self):
        return self.manager.purge_all()

    def assert_models_equal(self, m1, m2):
        self.assertTrue(model_eq(m1, m2),
                        "Models not equal:\na: %r\nb: %r" % (m1, m2))

    def assert_models_not_equal(self, m1, m2):
        self.assertFalse(model_eq(m1, m2),
                         "Models unexpectedly equal:\na: %r\nb: %r" % (m1, m2))

    @inlineCallbacks
    def test_new_conversation(self):
        conversations = yield self.store.list_conversations()
        self.assertEqual([], conversations)

        conv = yield self.store.new_conversation(
            u'bulk_message', u'subject', u'message')
        self.assertEqual(u'bulk_message', conv.conversation_type)
        self.assertEqual(u'subject', conv.subject)
        self.assertEqual(u'message', conv.message)
        self.assertEqual([], conv.batches.keys())

        dbconv = yield self.store.get_conversation_by_key(conv.key)
        self.assert_models_equal(conv, dbconv)
