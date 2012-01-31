# -*- coding: utf-8 -*-

"""Tests for go.vumitools.api_worker."""

from twisted.internet.defer import inlineCallbacks

from vumi.message import TransportEvent
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

    def publish_event(self, **kw):
        return self.dispatch(TransportEvent(**kw), rkey=self.rkey('event'))

    @inlineCallbacks
    def test_send(self):
        yield self.publish_command(VumiApiCommand.send('batch1', 'content',
                                                       'to_addr'))
        [msg] = yield self.get_dispatched_messages()
        self.assertEqual(msg['to_addr'], 'to_addr')
        self.assertEqual(msg['content'], 'content')

    @inlineCallbacks
    def test_consume_ack(self):
        yield self.publish_event(user_message_id='123', event_type='ack',
                                 sent_message_id='xyz')

    @inlineCallbacks
    def test_consume_delivery_report(self):
        yield self.publish_event(user_message_id='123',
                                 event_type='delivery_report',
                                 delivery_status='delivered')

    def test_consume_user_message(self):
        pass
