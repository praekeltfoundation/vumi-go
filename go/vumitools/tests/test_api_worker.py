# -*- coding: utf-8 -*-

"""Tests for go.vumitools.api_worker."""

from twisted.internet.defer import inlineCallbacks

from vumi.application.tests.test_base import ApplicationTestCase
from vumi.tests.utils import FakeRedis

from go.vumitools.api_worker import VumiApiWorker
from go.vumitools.api import VumiApiCommand


class TestVumiApiWorker(ApplicationTestCase):

    application_class = VumiApiWorker

    @inlineCallbacks
    def setUp(self):
        super(TestVumiApiWorker, self).setUp()
        self.api = yield self.get_application({})
        self.api.store.r_server = FakeRedis()

    def tearDown(self):
        self.api.store.r_server.teardown()
        super(TestVumiApiWorker, self).tearDown()

    def publish_command(self, cmd):
        return self.dispatch(cmd, rkey='vumi.api')

    @inlineCallbacks
    def test_send(self):
        yield self.publish_command(VumiApiCommand.send('batch1', 'content',
                                                       'to_addr'))
        [msg] = yield self.get_dispatched_messages()
        self.assertEqual(msg['to_addr'], 'to_addr')
        self.assertEqual(msg['content'], 'content')

    def test_consume_ack(self):
        pass

    def test_consume_delivery_report(self):
        pass

    def test_consume_user_message(self):
        pass
