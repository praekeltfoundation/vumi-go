"""Tests for go.vumitools.credit."""

import uuid

from twisted.internet.defer import inlineCallbacks

from vumi.tests.helpers import VumiTestCase, PersistenceHelper

from go.vumitools.credit import CreditManager


class TestCreditManager(VumiTestCase):

    @inlineCallbacks
    def setUp(self):
        self.persistence_helper = PersistenceHelper()
        self.add_cleanup(self.persistence_helper.cleanup)
        redis = yield self.persistence_helper.get_redis_manager()
        self.cm = CreditManager(redis)
        self.user_id = uuid.uuid4().hex

    @inlineCallbacks
    def test_get_credit(self):
        self.assertEqual((yield self.cm.get_credit(self.user_id)), None)
        yield self.cm.credit(self.user_id, 5)
        self.assertEqual((yield self.cm.get_credit(self.user_id)), 5)

    @inlineCallbacks
    def test_credit(self):
        self.assertEqual((yield self.cm.credit(self.user_id, 3)), 3)
        self.assertEqual((yield self.cm.credit(self.user_id, 5)), 8)

    @inlineCallbacks
    def test_debit(self):
        self.assertEqual((yield self.cm.debit(self.user_id, 1)), False)
        self.assertEqual((yield self.cm.get_credit(self.user_id)), 0)
        yield self.cm.credit(self.user_id, 10)
        self.assertEqual((yield self.cm.debit(self.user_id, 5)), True)
        self.assertEqual((yield self.cm.get_credit(self.user_id)), 5)
        self.assertEqual((yield self.cm.debit(self.user_id, 6)), False)
        self.assertEqual((yield self.cm.get_credit(self.user_id)), 5)
        self.assertEqual((yield self.cm.debit(self.user_id, 5)), True)
        self.assertEqual((yield self.cm.get_credit(self.user_id)), 0)
