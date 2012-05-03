"""Tests for go.vumitools.credit."""

import uuid

from twisted.trial.unittest import TestCase

from vumi.tests.utils import FakeRedis

from go.vumitools.credit import CreditManager


class TestCreditManager(TestCase):
    def setUp(self):
        self.r_server = FakeRedis()
        self.cm = CreditManager(self.r_server, "test_prefix")
        self.user_id = uuid.uuid4().hex

    def tearDown(self):
        self.r_server.teardown()

    def test_get_credit(self):
        self.assertEqual(self.cm.get_credit(self.user_id), None)
        self.cm.credit(self.user_id, 5)
        self.assertEqual(self.cm.get_credit(self.user_id), 5)

    def test_credit(self):
        self.assertEqual(self.cm.credit(self.user_id, 3), 3)
        self.assertEqual(self.cm.credit(self.user_id, 5), 8)

    def test_debit(self):
        self.assertEqual(self.cm.debit(self.user_id, 1), False)
        self.assertEqual(self.cm.get_credit(self.user_id), 0)
        self.cm.credit(self.user_id, 10)
        self.assertEqual(self.cm.debit(self.user_id, 5), True)
        self.assertEqual(self.cm.get_credit(self.user_id), 5)
        self.assertEqual(self.cm.debit(self.user_id, 6), False)
        self.assertEqual(self.cm.get_credit(self.user_id), 5)
        self.assertEqual(self.cm.debit(self.user_id, 5), True)
        self.assertEqual(self.cm.get_credit(self.user_id), 0)
