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

    @inlineCallbacks
    def setUp(self):
        super(TestBulkSendApplication, self).setUp()
        self._fake_redis = FakeRedis()
        self.api = yield self.get_application({
            'redis_cls': lambda **kw: self._fake_redis,
            })

    @inlineCallbacks
    def tearDown(self):
        self._fake_redis.teardown()
        yield self.api.manager.purge_all()
        yield super(TestBulkSendApplication, self).tearDown()

    def publish_command(self, cmd):
        return self.dispatch(cmd, rkey='%s.control' % (
                self.application_class.worker_name,))

    def publish_event(self, **kw):
        event = TransportEvent(**kw)
        d = self.dispatch(event, rkey=self.rkey('event'))
        d.addCallback(lambda _result: event)
        return d

    def store_outbound(self, **kw):
        return self.api.store.add_outbound_message(self.mkmsg_out(**kw))

    @inlineCallbacks
    def test_send(self):
        batch_id = yield self.api.store.batch_start([])
        yield self.publish_command(VumiApiCommand.send(batch_id,
                                                       'content',
                                                       {"from_addr": "from"},
                                                       'to_addr'))
        [msg] = yield self.get_dispatched_messages()
        self.assertEqual(msg['to_addr'], 'to_addr')
        self.assertEqual(msg['content'], 'content')

        self.assertEqual(self.api.store.batch_status(batch_id), {
                'ack': 0,
                'delivery_report': 0,
                'message': 1,
                'sent': 1,
                })
        [dbmsg] = yield self.api.store.batch_messages(batch_id)
        self.assertEqual(dbmsg, msg)

    @inlineCallbacks
    def test_consume_ack(self):
        yield self.store_outbound(message_id='123')
        ack_event = yield self.publish_event(user_message_id='123',
                                             event_type='ack',
                                             sent_message_id='xyz')
        [event] = yield self.api.store.message_events('123')
        self.assertEqual(event, ack_event)

    @inlineCallbacks
    def test_consume_delivery_report(self):
        yield self.store_outbound(message_id='123')
        dr_event = yield self.publish_event(user_message_id='123',
                                            event_type='delivery_report',
                                            delivery_status='delivered')
        [event] = yield self.api.store.message_events('123')
        self.assertEqual(event, dr_event)

    @inlineCallbacks
    def test_consume_user_message(self):
        msg = self.mkmsg_in()
        yield self.dispatch(msg)
        dbmsg = yield self.api.store.get_inbound_message(msg['message_id'])
        self.assertEqual(dbmsg, msg)

    @inlineCallbacks
    def test_close_session(self):
        msg = self.mkmsg_in(session_event=TransportUserMessage.SESSION_CLOSE)
        yield self.dispatch(msg)
        dbmsg = yield self.api.store.get_inbound_message(msg['message_id'])
        self.assertEqual(dbmsg, msg)
