# -*- coding: utf-8 -*-

"""Tests for go.vumitools.api."""

from twisted.trial.unittest import TestCase

from vumi.tests.utils import FakeRedis
from vumi.application.tests.test_base import ApplicationTestCase

from go.vumitools.api import MessageStore


class TestVumiApi(TestCase):
    # TODO: write tests
    pass


class TestMessageStore(ApplicationTestCase):
    # inherits from ApplicationTestCase for .mkmsg_in and .mkmsg_out

    def setUp(self):
        self.store = MessageStore({})
        self.store.r_server = FakeRedis()

    def tearDown(self):
        self.store.r_server.teardown()

    def test_batch_start(self):
        batch_id = self.store.batch_start()
        self.assertEqual(self.store.batch_messages(batch_id), [])
        self.assertEqual(self.store.batch_status(batch_id), {
            'ack': 0, 'delivery_report': 0, 'message': 0, 'sent': 0,
            })

    def test_add_message(self):
        batch_id = self.store.batch_start()
        msg = self.mkmsg_out(content="outfoo")
        self.store.add_message(batch_id, msg)

        self.assertEqual(self.store.get_message(msg['message_id']), msg)
        self.assertEqual(self.store.batch_status(batch_id), {
            'ack': 0, 'delivery_report': 0, 'message': 1, 'sent': 1,
            })


class TestMessageSender(TestCase):
    # TODO: write tests
    pass


class TestVumiApiCommand(TestCase):
    # TODO: write tests
    pass
