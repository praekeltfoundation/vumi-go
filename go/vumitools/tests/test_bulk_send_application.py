# -*- coding: utf-8 -*-

"""Tests for go.vumitools.bulk_send_application"""

from twisted.internet.defer import inlineCallbacks

from vumi.message import TransportEvent, TransportUserMessage
from vumi.application.tests.test_base import ApplicationTestCase
from vumi.tests.utils import FakeRedis

from go.vumitools.bulk_send_application import BulkSendApplication
from go.vumitools.api import VumiApiCommand


class TestBulkSendApplication(ApplicationTestCase):

    application_class = BulkSendApplication
    timeout = 1

    @inlineCallbacks
    def setUp(self):
        super(TestBulkSendApplication, self).setUp()
        self._fake_redis = FakeRedis()
        self.api = yield self.get_application({
            'redis_cls': lambda **kw: self._fake_redis,
            })

    def tearDown(self):
        self._fake_redis.teardown()
        super(TestBulkSendApplication, self).tearDown()

    def publish_command(self, cmd):
        return self.dispatch(cmd, rkey='%s.control' % (
                self.application_class.worker_name,))

    def publish_event(self, **kw):
        event = TransportEvent(**kw)
        d = self.dispatch(event, rkey=self.rkey('event'))
        d.addCallback(lambda _result: event)
        return d

    @inlineCallbacks
    def test_start(self):
        cmd = VumiApiCommand.command('dummy_worker', 'start',
            batch_id='batch1',
            to_addresses=['to_addr'],
            content='content',
            msg_options={
                'transport_type': 'sms',
                'from_addr': 'from_addr',
            })
        yield self.publish_command(cmd)
        [msg] = yield self.get_dispatched_messages()
        self.assertEqual(msg['to_addr'], 'to_addr')
        self.assertEqual(msg['content'], 'content')

        self.assertEqual(self.api.store.batch_status('batch1'), {
            'message': 1,
            'sent': 1,
            })
        [msg_id] = self.api.store.batch_messages('batch1')
        self.assertEqual(self.api.store.get_outbound_message(msg_id), msg)

    @inlineCallbacks
    def test_consume_ack(self):
        ack_event = yield self.publish_event(user_message_id='123',
                                             event_type='ack',
                                             sent_message_id='xyz')
        [event_id] = self.api.store.message_events('123')
        self.assertEqual(self.api.store.get_event(event_id), ack_event)

    @inlineCallbacks
    def test_consume_delivery_report(self):
        dr_event = yield self.publish_event(user_message_id='123',
                                            event_type='delivery_report',
                                            delivery_status='delivered')
        [event_id] = self.api.store.message_events('123')
        self.assertEqual(self.api.store.get_event(event_id), dr_event)

    @inlineCallbacks
    def test_consume_user_message(self):
        msg = self.mkmsg_in()
        yield self.dispatch(msg)
        self.assertEqual(self.api.store.get_inbound_message(msg['message_id']),
                         msg)

    @inlineCallbacks
    def test_close_session(self):
        msg = self.mkmsg_in(session_event=TransportUserMessage.SESSION_CLOSE)
        yield self.dispatch(msg)
        self.assertEqual(self.api.store.get_inbound_message(msg['message_id']),
                         msg)
