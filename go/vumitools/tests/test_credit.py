"""Tests for go.vumitools.credit."""

import uuid

from twisted.trial.unittest import TestCase
from twisted.internet.defer import inlineCallbacks

from go.vumitools.credit import CreditManager
from go.vumitools.tests.utils import GoPersistenceMixin


class TestCreditManager(TestCase, GoPersistenceMixin):

    @inlineCallbacks
    def setUp(self):
        self._persist_setUp()
        redis = yield self.get_redis_manager()
        self.cm = CreditManager(redis)
        self.user_id = uuid.uuid4().hex

    def tearDown(self):
        return self._persist_tearDown()

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
